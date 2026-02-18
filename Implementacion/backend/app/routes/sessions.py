# backend/app/routes/sessions.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId

from ...ml.bkt.bkt_runtime import (
    load_user_state,
    update_user_state_from_attempt,
    recommend_problems_for_user,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "math_tutor")

_client = MongoClient(MONGO_URI)
_db = _client[DB_NAME]

_sessions = _db["sessions"]
_attempts = _db["attempts"]
_problems = _db["problems"]


class StartSessionRequest(BaseModel):
    user_id: str
    k: int = Field(default=8, ge=1, le=20)  # number of problems in the daily session
    # Optional preference filters
    course: Optional[str] = None


class StartSessionResponse(BaseModel):
    session_id: str
    problem_ids: List[str]


@router.post("/start", response_model=StartSessionResponse)
def start_session(req: StartSessionRequest):
    # 1) load user knowledge state (BKT)
    state = load_user_state(user_id=req.user_id, db=_db)

    # 2) recommend problem docs (BKT + filters)
    recommended = recommend_problems_for_user(
        user_id=req.user_id,
        state=state,
        problems_collection=_problems,
        k=req.k,
        course=req.course,
    )
    problem_ids = [str(p["_id"]) for p in recommended]

    # 3) persist session
    doc = {
        "user_id": req.user_id,
        "created_at": datetime.utcnow(),
        "problem_ids": problem_ids,
        "course": req.course,
        "status": "active",
    }
    res = _sessions.insert_one(doc)
    return StartSessionResponse(session_id=str(res.inserted_id), problem_ids=problem_ids)


class AttemptRequest(BaseModel):
    user_id: str
    problem_id: str
    is_correct: bool
    # Optional: student free text answer, time spent, etc.
    student_answer: Optional[str] = None
    seconds_spent: Optional[int] = None


class AttemptResponse(BaseModel):
    ok: bool
    updated_mastery: Dict[str, float] = {}


@router.post("/{session_id}/attempt", response_model=AttemptResponse)
def submit_attempt(session_id: str, req: AttemptRequest):
    # Validate ids
    try:
        sid = ObjectId(session_id)
        pid = ObjectId(req.problem_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    sess = _sessions.find_one({"_id": sid})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    prob = _problems.find_one({"_id": pid})
    if not prob:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Store attempt
    _attempts.insert_one(
        {
            "session_id": sid,
            "user_id": req.user_id,
            "problem_id": pid,
            "is_correct": req.is_correct,
            "student_answer": req.student_answer,
            "seconds_spent": req.seconds_spent,
            "created_at": datetime.utcnow(),
            "kc": prob.get("kc"),
            "tags": prob.get("tags", []),
        }
    )

    # Update BKT state
    state = load_user_state(user_id=req.user_id, db=_db)
    new_state = update_user_state_from_attempt(
        state=state,
        kc=prob.get("kc"),
        is_correct=req.is_correct,
    )

    # Persist state
    _db["user_states"].update_one(
        {"user_id": req.user_id},
        {"$set": {"state": new_state, "updated_at": datetime.utcnow()}},
        upsert=True,
    )

    # Return mastery summary (example: mastery probability per KC)
    mastery = new_state.get("mastery", {})
    return AttemptResponse(ok=True, updated_mastery=mastery)


@router.get("/{session_id}")
def get_session(session_id: str):
    try:
        sid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    sess = _sessions.find_one({"_id": sid})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    sess["id"] = str(sess["_id"])
    del sess["_id"]
    return sess
