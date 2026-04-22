"""
ml/bkt/bkt_runtime.py
----------------------
Orchestration layer: reads from the database, drives the BKT update,
builds the performance state, and calls the HeuristicModel.

Responsibilities
----------------
  load_user_bkt_state       — read bkt_state dict from users collection
  update_bkt_after_attempt  — run BKT math and write result back to users collection
  build_performance_state   — aggregate attempt history into stats the HeuristicModel needs
  recommend_problems_for_user — full recommendation pipeline (entry point for sessions.py)

Nothing here does HTTP. Nothing here does BKT math directly — that lives in bkt_state.py.
Nothing here does heuristic scoring — that lives in heuristic.py.
This module is purely the glue.

Database assumptions
--------------------
  users     — one document per user, contains bkt_state and interests
  attempts  — one document per attempt, written by sessions.py on every submission
              Required fields: user_id, kc, tags, difficulty, course,
                               is_correct, seconds_spent, created_at

Performance note
----------------
  build_performance_state does a full scan of the user's attempts. Add a
  compound index on (user_id, created_at) to keep this fast as data grows:

      db.attempts.create_index([("user_id", 1), ("created_at", -1)])
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ml.bkt.bkt_state import (
    KCParams,
    GLOBAL_KC_PARAMS,
    bkt_update,
    is_mastered,
    cold_start_p_know,
)
from ml.bkt.heuristic import HeuristicModel, HeuristicConfig


# ---------------------------------------------------------------------------
# BKT state I/O
# ---------------------------------------------------------------------------

def load_user_bkt_state(user_id: str, db) -> Dict[str, Any]:
    """
    Return the bkt_state dict stored in the user document.
    Shape: { kc_id: { "p_know": float, "attempts": int, "mastered": bool, "last_updated": str } }
    Returns an empty dict if the user has no BKT history yet.
    """
    doc = db["users"].find_one({"user_id": user_id}, {"bkt_state": 1})
    if not doc:
        return {}
    return doc.get("bkt_state") or {}


def update_bkt_after_attempt(
    user_id: str,
    kc: Optional[str],
    is_correct: bool,
    db,
    kc_params: KCParams = GLOBAL_KC_PARAMS,
) -> Dict[str, Any]:
    """
    Run one BKT update step for the given KC and persist the result.

    Flow:
      1. Load current bkt_state and user's kc_scores (for cold start)
      2. Determine current p_know:
           - if KC already in bkt_state → use stored p_know
           - else → cold_start_p_know(interest_score) as prior
      3. Apply bkt_update
      4. Write updated entry back to users.bkt_state.<kc>
      5. Return the updated KC entry

    Parameters
    ----------
    user_id   : user identifier
    kc        : Knowledge Component id (may be None for untagged problems)
    is_correct: whether the student answered correctly
    db        : pymongo database handle
    kc_params : BKT parameters — use global defaults until per-KC fitting

    Returns
    -------
    The updated bkt_state entry for this KC, e.g.:
        {"p_know": 0.42, "attempts": 5, "mastered": False, "last_updated": "..."}
    Returns an empty dict if kc is None.
    """
    if not kc:
        return {}

    user_doc = db["users"].find_one(
        {"user_id": user_id},
        {"bkt_state": 1, "interests.kc_scores": 1}
    )

    existing_bkt  = (user_doc or {}).get("bkt_state") or {}
    kc_scores     = ((user_doc or {}).get("interests") or {}).get("kc_scores") or {}

    # Current p_know — use stored value or derive a cold-start prior
    current_entry = existing_bkt.get(kc)
    if current_entry:
        p_know   = float(current_entry.get("p_know", kc_params.p_know_init))
        attempts = int(current_entry.get("attempts", 0))
    else:
        p_know   = cold_start_p_know(kc_scores.get(kc))
        attempts = 0

    # Run BKT update
    new_p_know = bkt_update(p_know, is_correct, kc_params)
    mastered   = is_mastered(new_p_know, kc_params)

    updated_entry: Dict[str, Any] = {
        "p_know":       round(new_p_know, 6),
        "attempts":     attempts + 1,
        "mastered":     mastered,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    # Write back atomically — only touch this KC's entry
    db["users"].update_one(
        {"user_id": user_id},
        {"$set": {
            f"bkt_state.{kc}": updated_entry,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )

    return updated_entry


# ---------------------------------------------------------------------------
# Performance state builder (feeds the HeuristicModel)
# ---------------------------------------------------------------------------

def build_performance_state(user_id: str, db, recent_n: int = 20) -> Dict[str, Any]:
    """
    Aggregate the user's attempt history into the performance_state structure
    expected by HeuristicModel.

    Returns
    -------
    {
        "overall": {"attempts": int, "correct": int, "avg_seconds": float},
        "kc_stats": {
            kc: {"attempts": int, "correct": int, "avg_seconds": float}
        },
        "tag_stats": {
            kc: { tag: {"attempts": int, "correct": int, "avg_seconds": float} }
        },
        "difficulty_stats": {
            "1": {"attempts": int, "correct": int, "avg_seconds": float}, ...
        },
        "recent": {
            "kcs":          [kc, ...]   last recent_n kcs attempted
            "tags":         [tag, ...]  last recent_n first-tags attempted
            "difficulties": [int, ...]  last recent_n difficulties
            "courses":      [str, ...]  last recent_n courses
        }
    }

    NOTE: sort by created_at descending and reverse for chronological order
    so that "recent" truly means the most recent attempts.
    Requires index: db.attempts.create_index([("user_id", 1), ("created_at", -1)])
    """
    cursor = db["attempts"].find(
        {"user_id": user_id},
        {"kc": 1, "tags": 1, "is_correct": 1, "seconds_spent": 1,
         "difficulty": 1, "course": 1, "created_at": 1}
    ).sort("created_at", 1)   # ascending → process chronologically

    kc_stats:         Dict[str, Dict[str, Any]] = {}
    tag_stats:        Dict[str, Dict[str, Dict[str, Any]]] = {}
    difficulty_stats: Dict[str, Dict[str, Any]] = {}

    total_attempts = 0
    total_correct  = 0
    total_seconds  = 0

    recent_kcs          : List[str] = []
    recent_first_tags   : List[str] = []
    recent_difficulties : List[int] = []
    recent_courses      : List[str] = []

    for doc in cursor:
        kc         = doc.get("kc")
        tags       = doc.get("tags") or []
        is_correct = bool(doc.get("is_correct", False))
        seconds    = int(doc.get("seconds_spent") or 0)
        difficulty = doc.get("difficulty")
        course     = doc.get("course")

        total_attempts += 1
        if is_correct:
            total_correct += 1
        total_seconds += seconds

        # --- KC ---
        if kc:
            s = kc_stats.setdefault(kc, {"attempts": 0, "correct": 0, "total_seconds": 0})
            s["attempts"] += 1
            s["total_seconds"] += seconds
            if is_correct:
                s["correct"] += 1

        # --- Tags (nested under KC) ---
        if kc:
            for tag in tags:
                if not tag:
                    continue
                kc_tags = tag_stats.setdefault(kc, {})
                ts = kc_tags.setdefault(tag, {"attempts": 0, "correct": 0, "total_seconds": 0})
                ts["attempts"] += 1
                ts["total_seconds"] += seconds
                if is_correct:
                    ts["correct"] += 1

        # --- Difficulty ---
        if difficulty is not None:
            key = str(difficulty)
            ds = difficulty_stats.setdefault(key, {"attempts": 0, "correct": 0, "total_seconds": 0})
            ds["attempts"] += 1
            ds["total_seconds"] += seconds
            if is_correct:
                ds["correct"] += 1

        # --- Recent (keep rolling window, we'll slice at the end) ---
        if kc:
            recent_kcs.append(kc)
        if tags:
            recent_first_tags.append(str(tags[0]))
        if difficulty is not None:
            recent_difficulties.append(int(difficulty))
        if course:
            recent_courses.append(str(course))

    # --- Compute avg_seconds for all stat dicts ---
    def _finalize(stats_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out = {}
        for key, s in stats_dict.items():
            att = s["attempts"]
            out[key] = {
                "attempts":    att,
                "correct":     s["correct"],
                "avg_seconds": round(s["total_seconds"] / att, 2) if att > 0 else 90.0,
            }
        return out

    def _finalize_nested(nested: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        return {kc: _finalize(tag_map) for kc, tag_map in nested.items()}

    avg_seconds_overall = round(total_seconds / total_attempts, 2) if total_attempts > 0 else 90.0

    return {
        "overall": {
            "attempts":    total_attempts,
            "correct":     total_correct,
            "avg_seconds": avg_seconds_overall,
        },
        "kc_stats":         _finalize(kc_stats),
        "tag_stats":        _finalize_nested(tag_stats),
        "difficulty_stats": _finalize(difficulty_stats),
        "recent": {
            "kcs":          recent_kcs[-recent_n:],
            "tags":         recent_first_tags[-recent_n:],
            "difficulties": recent_difficulties[-recent_n:],
            "courses":      recent_courses[-recent_n:],
        },
    }


# ---------------------------------------------------------------------------
# Taxonomy builder
# ---------------------------------------------------------------------------

def build_taxonomy(problems_collection) -> Dict[str, List[str]]:
    """
    Derive the KC → [tags] map from the problems collection.
    This is the universe of KCs and tags the model can recommend.
    """
    taxonomy: Dict[str, set] = {}
    cursor = problems_collection.find(
        {"kc": {"$exists": True}, "tags": {"$exists": True}},
        {"kc": 1, "tags": 1}
    )
    for doc in cursor:
        kc   = doc.get("kc")
        tags = doc.get("tags") or []
        if not kc:
            continue
        taxonomy.setdefault(kc, set()).update(str(t) for t in tags if t)
    return {kc: sorted(list(tags)) for kc, tags in taxonomy.items() if tags}


# ---------------------------------------------------------------------------
# Effective BKT state (cold-start aware)
# ---------------------------------------------------------------------------

def build_effective_bkt_state(
    stored_bkt_state: Dict[str, Any],
    kc_scores: Dict[str, float],
    taxonomy: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Return a BKT state entry for every KC in the taxonomy.

    For KCs already in stored_bkt_state → use the stored entry as-is.
    For KCs not yet attempted → generate a cold-start entry using
    cold_start_p_know(interest_score) so the HeuristicModel always
    has a full picture without requiring eager initialization.

    This is never written to the database — it is an ephemeral view
    used only during recommendation.
    """
    effective: Dict[str, Any] = {}
    for kc in taxonomy:
        if kc in stored_bkt_state:
            effective[kc] = stored_bkt_state[kc]
        else:
            p0 = cold_start_p_know(kc_scores.get(kc))
            effective[kc] = {
                "p_know":   p0,
                "attempts": 0,
                "mastered": False,
            }
    return effective


# ---------------------------------------------------------------------------
# Problem lookup
# ---------------------------------------------------------------------------

def find_matching_problem(
    problems_collection,
    course: str,
    kc: str,
    tag: str,
    difficulty: int,
    used_ids: set,
) -> Optional[Dict[str, Any]]:
    """
    Find a problem matching the spec. Falls back progressively:
      1. exact match: course + kc + tag + difficulty
      2. relax difficulty: course + kc + tag
      3. relax tag: course + kc
    Returns None if nothing is found even after fallbacks.
    """
    def _query_and_filter(query: Dict) -> Optional[Dict]:
        candidates = [
            p for p in problems_collection.find(query).limit(100)
            if str(p["_id"]) not in used_ids
        ]
        return random.choice(candidates) if candidates else None

    return (
        _query_and_filter({"course": course, "kc": kc, "tags": tag, "difficulty": difficulty})
        or _query_and_filter({"course": course, "kc": kc, "tags": tag})
        or _query_and_filter({"course": course, "kc": kc})
    )


# ---------------------------------------------------------------------------
# Main recommendation entry point
# ---------------------------------------------------------------------------

def recommend_problems_for_user(
    user_id: str,
    state: Dict[str, Any],
    problems_collection,
    k: int = 8,
    course: Optional[str] = None,
    db=None,
) -> List[Dict[str, Any]]:
    """
    Full recommendation pipeline.

    Parameters
    ----------
    user_id             : user identifier
    state               : full user document (profile + interests + bkt_state + progress)
    problems_collection : pymongo collection handle
    k                   : number of problems to recommend
    course              : override course level (optional)
    db                  : pymongo database handle (needed for performance_state)

    Returns
    -------
    List of problem documents (pymongo dicts with _id etc.)
    """
    profile      = state.get("profile") or {}
    interests    = state.get("interests") or {}
    diff_prefs   = interests.get("difficulty_preferences") or {}
    session_prefs= interests.get("session_preferences") or {}

    course_level      = course or profile.get("course_level", "1º ESO")
    allow_cross_course= bool(profile.get("allow_cross_course", False))
    objective         = interests.get("primary_objective", "PRACTICE")
    kc_scores         = interests.get("kc_scores") or {}
    tag_scores        = interests.get("tag_scores") or {}

    min_difficulty    = int(diff_prefs.get("min_difficulty", 1))
    max_difficulty    = int(diff_prefs.get("max_difficulty", 3))
    target_difficulty = int(diff_prefs.get("target_difficulty", 2))

    # --- Build taxonomy ---
    taxonomy = build_taxonomy(problems_collection)
    if not taxonomy:
        return []

    # --- Build performance state (heuristic inputs) ---
    performance_state = build_performance_state(user_id, db) if db else {}

    # --- Build effective BKT state (BKT inputs, cold-start aware) ---
    stored_bkt = state.get("bkt_state") or {}
    effective_bkt = build_effective_bkt_state(stored_bkt, kc_scores, taxonomy)

    # --- Run HeuristicModel ---
    model = HeuristicModel(
        course_level=course_level,
        allow_cross_course=allow_cross_course,
        kc_scores=kc_scores,
        tag_scores=tag_scores,
        taxonomy=taxonomy,
        min_difficulty=min_difficulty,
        max_difficulty=max_difficulty,
        target_difficulty=target_difficulty,
        primary_objective=objective,
        performance_state=performance_state,
        bkt_state=effective_bkt,        # ← BKT feeds in here
        seed=None,
    )

    n = min(k, int(session_prefs.get("problems_per_session", k)))
    specs = model.generate_session(n)

    # --- Fetch actual problems from DB ---
    selected : List[Dict[str, Any]] = []
    used_ids : set = set()

    for rec_course, rec_kc, rec_tag, rec_difficulty in specs:
        problem = find_matching_problem(
            problems_collection=problems_collection,
            course=rec_course,
            kc=rec_kc,
            tag=rec_tag,
            difficulty=rec_difficulty,
            used_ids=used_ids,
        )
        if problem is not None:
            selected.append(problem)
            used_ids.add(str(problem["_id"]))

    return selected


# ---------------------------------------------------------------------------
# Backward-compat shim (used by sessions.py load_user_state call)
# ---------------------------------------------------------------------------

def load_user_state(user_id: str, db) -> Dict[str, Any]:
    """Load the full user document. Returns a default skeleton if not found."""
    doc = db["users"].find_one({"user_id": user_id})
    if doc:
        return doc
    return {
        "user_id": user_id,
        "profile": {"course_level": "1º ESO", "modality": None, "allow_cross_course": False},
        "interests": {
            "primary_objective": "PRACTICE",
            "kc_scores": {}, "tag_scores": {},
            "difficulty_preferences": {"min_difficulty": 1, "max_difficulty": 3, "target_difficulty": 2, "trend": "STABLE"},
            "session_preferences":    {"problems_per_session": 5, "sessions_per_week": 4},
            "problem_preferences":    {"repetition_preference": "MEDIUM", "statement_length_preference": "MEDIUM", "multi_topic_preference": "NO_PREFERENCE"},
        },
        "bkt_state": {},
        "progress": {"completed_problems": 0, "correct_attempts": 0, "total_attempts": 0, "streak": 0},
    }