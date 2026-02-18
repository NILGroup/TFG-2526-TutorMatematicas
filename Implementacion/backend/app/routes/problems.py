# backend/app/routes/problems.py
from __future__ import annotations

import os
import random
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId

router = APIRouter(prefix="/problems", tags=["problems"])

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "math_tutor")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "problems")

_client = MongoClient(MONGO_URI)
_db = _client[DB_NAME]
_problems = _db[COLLECTION_NAME]


def _instantiate_parameters(parameters: Dict[str, Any]) -> Dict[str, int]:
    """
    Your parametric engine (runtime instantiation).
    For now, supports {"a":[min,max], ...} -> {"a": int}
    """
    inst: Dict[str, int] = {}
    for k, v in (parameters or {}).items():
        if isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v):
            inst[k] = random.randint(v[0], v[1])
    return inst


class ProblemOut(BaseModel):
    id: str
    course: Optional[str] = None
    kc: Optional[str] = None
    tags: List[str] = []
    difficulty: Optional[int] = None
    statement: str
    parameters: Dict[str, Any] = {}
    instantiated_parameters: Dict[str, int] = {}


@router.get("/", response_model=List[ProblemOut])
def list_problems(
    course: Optional[str] = Query(default=None),
    kc: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    difficulty: Optional[int] = Query(default=None, ge=1, le=5),
    limit: int = Query(default=20, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
):
    query: Dict[str, Any] = {}
    if course:
        query["course"] = course
    if kc:
        query["kc"] = kc
    if tag:
        query["tags"] = tag
    if difficulty is not None:
        query["difficulty"] = difficulty

    docs = _problems.find(query).skip(skip).limit(limit)
    out: List[ProblemOut] = []
    for d in docs:
        out.append(
            ProblemOut(
                id=str(d["_id"]),
                course=d.get("course"),
                kc=d.get("kc"),
                tags=d.get("tags", []),
                difficulty=d.get("difficulty"),
                statement=d.get("statement", ""),
                parameters=d.get("parameters", {}) or {},
                instantiated_parameters=_instantiate_parameters(d.get("parameters", {}) or {}),
            )
        )
    return out


@router.get("/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: str):
    try:
        oid = ObjectId(problem_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid problem_id format")

    d = _problems.find_one({"_id": oid})
    if not d:
        raise HTTPException(status_code=404, detail="Problem not found")

    return ProblemOut(
        id=str(d["_id"]),
        course=d.get("course"),
        kc=d.get("kc"),
        tags=d.get("tags", []),
        difficulty=d.get("difficulty"),
        statement=d.get("statement", ""),
        parameters=d.get("parameters", {}) or {},
        instantiated_parameters=_instantiate_parameters(d.get("parameters", {}) or {}),
    )
