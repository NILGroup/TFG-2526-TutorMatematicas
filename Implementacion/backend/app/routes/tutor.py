# backend/app/routes/tutor.py
from __future__ import annotations

import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId

from ...ml.chatbot.chatbot import generate_tutor_answer

router = APIRouter(prefix="/tutor", tags=["tutor"])


# ---------- DB wiring (simple version) ----------
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "math_tutor")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "problems")

_client = MongoClient(MONGO_URI)
_db = _client[DB_NAME]
_problems = _db[COLLECTION_NAME]


# ---------- Request/Response models ----------
class TutorChatRequest(BaseModel):
    problem_id: str = Field(..., description="MongoDB _id of the problem document")
    question: str = Field(..., min_length=1, description="Student question about this problem")
    # Optional fields you may add later:
    user_id: Optional[str] = None
    current_attempt: Optional[str] = None


class TutorChatResponse(BaseModel):
    answer: str
    meta: Dict[str, Any] = {}


@router.post("/chat", response_model=TutorChatResponse)
def tutor_chat(req: TutorChatRequest) -> TutorChatResponse:
    # 1) Parse ObjectId
    try:
        oid = ObjectId(req.problem_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid problem_id format")

    # 2) Fetch problem context
    problem = _problems.find_one({"_id": oid})
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # 3) Call ML module (direct Python call, not HTTP)
    try:
        text = generate_tutor_answer(
            problem=problem,
            student_question=req.question,
            current_attempt=req.current_attempt,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chatbot failed: {e}")

    return TutorChatResponse(
        answer=text,
        meta={
            "problem_id": req.problem_id,
            "kc": problem.get("kc"),
            "tags": problem.get("tags", []),
        },
    )
