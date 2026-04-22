# app/routes/users.py
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient

router = APIRouter(prefix="/users", tags=["users"])

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.environ.get("DB_NAME",   "math_tutor")

_client = MongoClient(MONGO_URI)
_db     = _client[DB_NAME]
_users  = _db["users"]


def utcnow():
    return datetime.now(timezone.utc)


def default_user_document(user_id: str) -> Dict[str, Any]:
    return {
        "user_id":    user_id,
        "name":       user_id,
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "profile": {
            "course_level":      "3º ESO",
            "modality":          None,
            "allow_cross_course": False,
        },
        "interests": {
            "primary_objective": "PRACTICE",
            "kc_scores":  {},
            "tag_scores":  {},
            "difficulty_preferences": {
                "min_difficulty":    1,
                "max_difficulty":    3,
                "target_difficulty": 2,
                "trend":             "STABLE",
            },
            "session_preferences": {
                "problems_per_session": 5,
                "sessions_per_week":    4,
            },
            "problem_preferences": {
                "repetition_preference":        "MEDIUM",
                "statement_length_preference":  "MEDIUM",
                "multi_topic_preference":       "NO_PREFERENCE",
            },
        },
        # BKT knowledge state per KC.
        # Populated lazily: an entry is created the first time the student
        # attempts a problem tagged with that KC (see bkt_runtime.update_bkt_after_attempt).
        # Shape: { kc_id: { "p_know": float, "attempts": int, "mastered": bool, "last_updated": str } }
        "bkt_state": {},
        "runtime": {
            "last_session_at":          None,
            "last_recommendation_seed": None,
        },
        "progress": {
            "completed_problems": 0,
            "correct_attempts":   0,
            "total_attempts":     0,
            "streak":             0,
        },
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DifficultyPreferences(BaseModel):
    min_difficulty:    int = Field(default=1, ge=1, le=5)
    max_difficulty:    int = Field(default=3, ge=1, le=5)
    target_difficulty: int = Field(default=2, ge=1, le=5)
    trend: str = "STABLE"


class SessionPreferences(BaseModel):
    problems_per_session: int = Field(default=5, ge=1, le=20)
    sessions_per_week:    int = Field(default=4, ge=1, le=7)


class ProblemPreferences(BaseModel):
    repetition_preference:       str = "MEDIUM"
    statement_length_preference: str = "MEDIUM"
    multi_topic_preference:      str = "NO_PREFERENCE"


class UserInterestsPayload(BaseModel):
    user_id:       str
    course_level:  str
    modality:      Optional[str] = None
    allow_cross_course: bool = False
    primary_objective:  str  = "PRACTICE"
    kc_scores:     Dict[str, float]            = {}
    tag_scores:    Dict[str, Dict[str, float]] = {}
    difficulty_preferences: DifficultyPreferences = DifficultyPreferences()
    session_preferences:    SessionPreferences    = SessionPreferences()
    problem_preferences:    ProblemPreferences    = ProblemPreferences()


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------

@router.get("/{user_id}")
def get_user(user_id: str):
    doc = _users.find_one({"user_id": user_id})
    if not doc:
        doc = default_user_document(user_id)
        _users.insert_one(doc)
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# ---------------------------------------------------------------------------
# PUT /users/{user_id}/interests
# ---------------------------------------------------------------------------

@router.put("/{user_id}/interests")
def update_user_interests(user_id: str, payload: UserInterestsPayload):
    if payload.user_id != user_id:
        raise HTTPException(status_code=400, detail="user_id mismatch")

    # Create user document if it doesn't exist yet
    if not _users.find_one({"user_id": user_id}, {"_id": 1}):
        _users.insert_one(default_user_document(user_id))

    update = {
        "profile.course_level":       payload.course_level,
        "profile.modality":           payload.modality,
        "profile.allow_cross_course": payload.allow_cross_course,

        "interests.primary_objective":   payload.primary_objective,
        "interests.kc_scores":           payload.kc_scores,
        "interests.tag_scores":          payload.tag_scores,
        "interests.difficulty_preferences": payload.difficulty_preferences.model_dump(),
        "interests.session_preferences":    payload.session_preferences.model_dump(),
        "interests.problem_preferences":    payload.problem_preferences.model_dump(),

        "updated_at": utcnow(),
    }

    # bkt_state is intentionally NOT reset here.
    # Interest scores changing does not erase accumulated knowledge evidence.
    # Cold-start logic in bkt_runtime.build_effective_bkt_state handles
    # new KCs that appear in kc_scores but have no bkt_state entry yet.

    _users.update_one({"user_id": user_id}, {"$set": update}, upsert=True)
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /users/{user_id}/bkt  — inspect BKT state (useful for frontend/debug)
# ---------------------------------------------------------------------------

@router.get("/{user_id}/bkt")
def get_user_bkt(user_id: str):
    """
    Return the current BKT state for all KCs the user has attempted.
    Useful for progress dashboards and debugging.
    """
    doc = _users.find_one({"user_id": user_id}, {"bkt_state": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id, "bkt_state": doc.get("bkt_state") or {}}