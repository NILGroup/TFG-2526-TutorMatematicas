# backend/ml/bkt/bkt_runtime.py
from __future__ import annotations

from typing import Dict, Any, Optional, List
import random


def load_user_state(user_id: str, db) -> Dict[str, Any]:
    """
    Load user BKT state from MongoDB.
    Expected collection: user_states with {user_id, state:{...}}
    """
    doc = db["user_states"].find_one({"user_id": user_id})
    if doc and "state" in doc:
        return doc["state"]

    # Default empty state
    return {"mastery": {}}  # mastery[kc] = probability


def update_user_state_from_attempt(state: Dict[str, Any], kc: Optional[str], is_correct: bool) -> Dict[str, Any]:
    """
    Placeholder update logic.
    Replace this with real BKT update equations later.
    """
    if not kc:
        return state

    mastery = dict(state.get("mastery", {}))
    p = float(mastery.get(kc, 0.3))
    # naive update rule
    if is_correct:
        p = min(0.95, p + 0.10)
    else:
        p = max(0.05, p - 0.08)
    mastery[kc] = p
    return {"mastery": mastery}


def recommend_problems_for_user(
    user_id: str,
    state: Dict[str, Any],
    problems_collection,
    k: int = 8,
    course: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Placeholder recommender:
    - Prefer problems in KCs where mastery is low.
    - If no mastery yet, random sample.
    """
    mastery = state.get("mastery", {}) or {}

    query = {}
    if course:
        query["course"] = course

    # Pull a candidate pool
    candidates = list(problems_collection.find(query).limit(500))
    if not candidates:
        return []

    # Score by (1 - mastery[kc]) + small noise
    def score(p):
        kc = p.get("kc")
        m = float(mastery.get(kc, 0.3))
        return (1.0 - m) + random.random() * 0.05

    candidates.sort(key=score, reverse=True)
    return candidates[:k]
