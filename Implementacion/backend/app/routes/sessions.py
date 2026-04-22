# app/routes/sessions.py
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId

from ml.bkt.bkt_runtime import (
    load_user_state,
    update_bkt_after_attempt,
    recommend_problems_for_user,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.environ.get("DB_NAME",   "math_tutor")

_client   = MongoClient(MONGO_URI)
_db       = _client[DB_NAME]
_sessions = _db["sessions"]
_attempts = _db["attempts"]
_problems = _db["problems"]
_users    = _db["users"]


# ---------------------------------------------------------------------------
# POST /sessions/start
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    user_id: str
    k: int = Field(default=8, ge=1, le=20)
    course: Optional[str] = None


class StartSessionResponse(BaseModel):
    session_id: str
    problem_ids: List[str]


@router.post("/start", response_model=StartSessionResponse)
def start_session(req: StartSessionRequest):
    # 1) Load full user state (profile + interests + bkt_state)
    state = load_user_state(user_id=req.user_id, db=_db)

    # 2) Recommend problems — BKT + heuristic pipeline
    recommended = recommend_problems_for_user(
        user_id=req.user_id,
        state=state,
        problems_collection=_problems,
        k=req.k,
        course=req.course,
        db=_db,
    )
    problem_ids = [str(p["_id"]) for p in recommended]

    # 3) Persist session document
    doc = {
        "user_id":    req.user_id,
        "created_at": datetime.now(timezone.utc),
        "problem_ids":problem_ids,
        "course":     req.course,
        "status":     "active",
    }
    res = _sessions.insert_one(doc)
    return StartSessionResponse(session_id=str(res.inserted_id), problem_ids=problem_ids)


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/attempt
# ---------------------------------------------------------------------------

class AttemptRequest(BaseModel):
    user_id: str
    problem_id: str
    is_correct: bool
    student_answer: Optional[str] = None
    seconds_spent: Optional[int] = None


class AttemptResponse(BaseModel):
    ok: bool
    kc: Optional[str] = None
    p_know: Optional[float] = None
    mastered: Optional[bool] = None


@router.post("/{session_id}/attempt", response_model=AttemptResponse)
def submit_attempt(session_id: str, req: AttemptRequest):
    # --- Validate ObjectIds ---
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

    kc         = prob.get("kc")
    tags       = prob.get("tags") or []
    difficulty = prob.get("difficulty")
    course     = prob.get("course")

    # 1) Record attempt — include all fields needed by build_performance_state
    _attempts.insert_one({
        "session_id":     sid,
        "user_id":        req.user_id,
        "problem_id":     pid,
        "is_correct":     req.is_correct,
        "student_answer": req.student_answer,
        "seconds_spent":  req.seconds_spent,
        "created_at":     datetime.now(timezone.utc),
        # Denormalized from problem — avoids joins in build_performance_state
        "kc":             kc,
        "tags":           tags,
        "difficulty":     difficulty,
        "course":         course,
    })

    # 2) BKT update — runs math, writes bkt_state back to user document
    updated_kc_entry = update_bkt_after_attempt(
        user_id=req.user_id,
        kc=kc,
        is_correct=req.is_correct,
        db=_db,
    )

    # 3) Update global progress counters
    inc: Dict[str, Any] = {"progress.total_attempts": 1}
    if req.is_correct:
        inc["progress.correct_attempts"] = 1
    _users.update_one(
        {"user_id": req.user_id},
        {"$inc": inc, "$set": {"updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

    return AttemptResponse(
        ok=True,
        kc=kc,
        p_know=updated_kc_entry.get("p_know"),
        mastered=updated_kc_entry.get("mastered"),
    )


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}
# ---------------------------------------------------------------------------

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