#!/usr/bin/env python3
"""
transformer.py
==============

Offline dataset transformation pipeline.

- Loads math problems from a Hugging Face dataset (placeholder configurable).
- Uses DeepSeek-R1 via Ollama (local) to transform problems into a structured JSON format.
- Enforces taxonomy and KC/tag consistency using kc_tags.json and taxonomy.in.
- Optionally validates mathematical correctness + semantic tag fit using Mathstral.
- Stores final results in MongoDB (math_tutor.problems).

This script is meant to be run occasionally, not as part of the live backend.
"""

import argparse
import json
import random
import time
from typing import Dict, Any, List, Optional, Tuple

import requests
from pymongo import MongoClient
from datasets import load_dataset


# =========================
# CONFIGURATION
# =========================

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODELS = {
    "generator": "deepseek-r1:latest",
    "validator": "mathstral:latest",
}

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "math_tutor"
COLLECTION_NAME = "problems"

# Only allowed course identifiers in your dataset schema.
# Keep these consistent across prompting + validation.
ALLOWED_COURSES = {
    "1º ESO",
    "2º ESO",
    "3º ESO",
    "4º ESO",
    "1º Bach",
    "2º Bach",
}


# =========================
# UTILS
# =========================

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def ollama_chat(model: str, prompt: str, temperature: float = 0.2) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise and reliable mathematics assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {"temperature": temperature}
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def safe_json_extract(text: str) -> dict:
    """
    Extract a JSON object from model output, even if it contains extra text.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start:end+1])


# =========================
# PARAMETRIC ENGINE (OPTIONAL)
# =========================

def instantiate_parameters(parameters: Dict[str, List[int]]) -> Dict[str, int]:
    """
    Given:
      {"a": [1,5], "b": [-2,3]}
    Return:
      {"a": 3, "b": -1}
    """
    inst = {}
    for k, v in parameters.items():
        if isinstance(v, list) and len(v) == 2:
            inst[k] = random.randint(v[0], v[1])
    return inst


# =========================
# PROMPTING
# =========================

def build_phase_a_prompt(
    raw_problem: str,
    source_dataset: str,
    source_split: str,
    source_index: int,
    taxonomy: str,
    kc_tags: dict
) -> str:
    """
    Build a prompt for Phase A: classify the raw problem into course, kc, tags, and difficulty.

    The model must output ONLY a JSON object with these fields:
      - course: one of ALLOWED_COURSES
      - kc: one key from kc_tags["kcs"]
      - tags: a list of allowed tags corresponding to the chosen kc
      - difficulty: integer from 1–5

    We include the taxonomy and allowed lists to guide the model.
    """
    kc_list = list(kc_tags["kcs"].keys())
    all_tags = sorted(
        set(
            tag
            for kc in kc_tags["kcs"].values()
            for tag in kc["maps_from_tags"]
        )
    )
    course_options = " | ".join(sorted(ALLOWED_COURSES))
    return f"""
You are classifying a math problem for a Spanish high-school tutoring dataset.

You MUST output ONLY a JSON object with EXACTLY these keys:
  "course": one of the allowed courses listed below
  "kc": one of the allowed knowledge components (kc) listed below
  "tags": a non-empty array of tags, chosen from the allowed tags below and consistent with the selected kc
  "difficulty": an integer from 1 to 5 indicating problem difficulty

========================
SOURCE METADATA
========================
source_dataset: {source_dataset}
source_split: {source_split}
source_index: {source_index}

========================
TAXONOMY (COURSES & TOPICS)
========================
{taxonomy}

========================
ALLOWED COURSES
========================
{sorted(ALLOWED_COURSES)}

========================
ALLOWED KNOWLEDGE COMPONENTS (kc)
========================
{kc_list}

========================
ALLOWED TAGS
========================
{all_tags}

========================
RAW PROBLEM
========================
{raw_problem}

========================
TASK
========================
Return a JSON object with keys "course", "kc", "tags", and "difficulty" as described.
Do NOT include statement, parameters, solution steps, or answer in this phase.
Output ONLY valid JSON.
"""


def build_phase_b_prompt(
    raw_problem: str,
    classification: dict
) -> str:
    """
    Build a prompt for Phase B: generate a normalized Spanish statement, parameters, and final answer.

    We provide the classification result (course, kc, tags, difficulty) for context. The model should output
    a JSON object with keys "statement", "parameters", and "answer".

    - statement: Spanish rephrasing of the problem including parameters instead of specific numbers where appropriate.
    - parameters: an object mapping parameter names to [min,max] integer ranges, or empty if not parametrizable.
    - answer: the final numerical or algebraic answer.
    """
    course = classification.get("course", "")
    kc = classification.get("kc", "")
    tags = classification.get("tags", [])
    difficulty = classification.get("difficulty", "")
    return f"""
You are rewriting and solving a math problem for a Spanish high-school tutoring dataset.

Based on the classification below, produce a JSON object with keys:
  "statement": a clear Spanish statement of the problem, using symbolic parameters instead of specific numbers when appropriate;
  "parameters": an object mapping parameter names to [min,max] integer ranges used in the statement (if the problem can be parameterized), otherwise an empty object;
  "answer": the final answer (numeric or algebraic, in Spanish format where needed).

========================
CLASSIFICATION
========================
course: {course}
kc: {kc}
tags: {tags}
difficulty: {difficulty}

========================
RAW PROBLEM
========================
{raw_problem}

========================
TASK
========================
Return a JSON object with keys "statement", "parameters", and "answer" exactly. Do not include course, kc, tags, difficulty, or solution steps here.
Use only valid JSON.
"""


def build_phase_c_prompt(
    raw_problem: str,
    classification: dict,
    statement: str,
    answer: str,
    parameters: dict
) -> str:
    """
    Build a prompt for Phase C: generate the solution steps.

    The model should output a JSON object with a single key "solution_steps" which is an ordered list of Spanish sentences
    explaining the reasoning leading from the statement to the final answer. It should reference the parameters where appropriate.
    """
    course = classification.get("course", "")
    kc = classification.get("kc", "")
    tags = classification.get("tags", [])
    difficulty = classification.get("difficulty", "")
    return f"""
You are a math tutor writing step-by-step solution for a Spanish high-school math problem.

========================
CONTEXT
========================
course: {course}
kc: {kc}
tags: {tags}
difficulty: {difficulty}
Statement (Spanish):
{statement}

Parameters:
{parameters}

Final answer:
{answer}

========================
TASK
========================
Return a JSON object with key "solution_steps" containing an array of Spanish sentences.
Each sentence should be clear and reflect a logical step towards obtaining the final answer.
Use the parameter names in your reasoning where appropriate.
Output ONLY valid JSON.
"""


# =========================
# VALIDATION (HARD + SOFT)
# =========================

def validate_with_mathstral(
    problem: Dict[str, Any],
    kc_tags: Dict[str, Any],
    taxonomy: Optional[str] = None,
    semantic_check: bool = True,
    return_reason: bool = False
) -> bool | Tuple[bool, str]:
    """
    Validates:
      A) Deterministic schema/tag/KC consistency using kc_tags.json
      B) (Optional) Semantic sanity using Mathstral via Ollama:
         - math correctness
         - tag appropriateness given the statement/steps

    Args:
      problem: dict produced by transformer
      kc_tags: loaded kc_tags.json (as dict)
      taxonomy: (optional) text from taxonomy.in (can be long; we pass only a short excerpt if provided)
      semantic_check: if True, calls Mathstral to validate math + semantic tag fit
      return_reason: if True, returns (bool, reason)

    Returns:
      bool or (bool, reason)
    """

    def fail(msg: str):
        return (False, msg) if return_reason else False

    # ---------- A) HARD VALIDATION (no LLM) ----------
    required_fields = ["course", "kc", "tags", "statement", "solution_steps", "answer"]
    for f in required_fields:
        if f not in problem:
            return fail(f"Missing required field: {f}")

    # Basic type checks
    if not isinstance(problem["tags"], list):
        return fail("Field 'tags' must be a list.")
    if not isinstance(problem["solution_steps"], list):
        return fail("Field 'solution_steps' must be a list.")

    # Course check
    course = str(problem.get("course", "")).strip()
    if course not in ALLOWED_COURSES:
        return fail(f"Invalid course '{course}'. Must be one of: {sorted(ALLOWED_COURSES)}")

    # KC must exist
    kc = str(problem.get("kc", "")).strip()
    kcs = kc_tags.get("kcs", {})
    if kc not in kcs:
        return fail(f"KC '{kc}' not found in kc_tags.json")

    # Build global tag vocabulary
    global_vocab = set()
    for kc_def in kcs.values():
        for t in kc_def.get("maps_from_tags", []):
            global_vocab.add(str(t).strip())

    # Normalise tags
    tags = [str(t).strip() for t in problem.get("tags", []) if str(t).strip()]

    # All tags must be known
    unknown_tags = [t for t in tags if t not in global_vocab]
    if unknown_tags:
        return fail(f"Unknown tags not in kc_tags.json vocabulary: {unknown_tags}")

    # Tags must belong to the selected KC
    allowed_for_kc = set(str(t).strip() for t in kcs[kc].get("maps_from_tags", []))
    not_in_kc = [t for t in tags if t not in allowed_for_kc]
    if not_in_kc:
        return fail(
            f"Tags not allowed for KC '{kc}': {not_in_kc}. "
            f"Allowed tags for this KC are: {sorted(allowed_for_kc)}"
        )

    # If we only want hard validation
    if not semantic_check:
        return (True, "OK (hard validation only)") if return_reason else True

    # ---------- B) SOFT VALIDATION (Mathstral LLM) ----------
    taxonomy_excerpt = ""
    if taxonomy:
        taxonomy_excerpt = taxonomy[:1200]  # keep prompt bounded

    kc_desc = kcs[kc].get("description", "")
    kc_allowed_list = sorted(list(allowed_for_kc))

    prompt = f"""
You are validating a structured math-problem record for a Spanish high-school tutor dataset.

Your tasks:
1) Check whether the FINAL ANSWER is consistent with the STATEMENT and the SOLUTION STEPS.
2) Check whether the chosen KC and TAGS make semantic sense for this problem.
3) If something is clearly wrong, mark INVALID.

Context (taxonomy excerpt, optional):
{taxonomy_excerpt}

Selected course: {course}

Selected KC: {kc}
KC description: {kc_desc}

Allowed tags for this KC:
{kc_allowed_list}

Proposed tags:
{tags}

STATEMENT:
{problem['statement']}

SOLUTION STEPS:
{problem['solution_steps']}

ANSWER:
{problem['answer']}

Respond ONLY with:
VALID
or
INVALID
No extra text.
"""

    try:
        result = ollama_chat(OLLAMA_MODELS["validator"], prompt, temperature=0.0)
        up = result.upper()
        ok = ("VALID" in up) and ("INVALID" not in up)
        if return_reason:
            return (ok, "OK (hard+soft validation)" if ok else "Mathstral marked INVALID")
        return ok
    except Exception as e:
        return fail(f"Mathstral validation call failed: {e}")


# =========================
# MAIN PIPELINE
# =========================

# ==== Phase processors ====

def process_phase_a(
    ds,
    source_dataset: str,
    source_split: str,
    kc_tags: dict,
    taxonomy: str,
    max_samples: Optional[int],
    collection,
    dry_run: bool,
):
    """Run Phase A: classify problems into course/kc/tags/difficulty."""
    for i, ex in enumerate(ds):
        if max_samples is not None and i >= max_samples:
            break
        raw_problem = ex.get("question") or ex.get("problem") or str(ex)
        prompt = build_phase_a_prompt(
            raw_problem=raw_problem,
            source_dataset=source_dataset,
            source_split=source_split,
            source_index=i,
            taxonomy=taxonomy,
            kc_tags=kc_tags,
        )
        try:
            output = ollama_chat(OLLAMA_MODELS["generator"], prompt, temperature=0.2)
            classification = safe_json_extract(output)
        except Exception as e:
            print(f"[ERROR] Phase A failed at index {i}: {e}")
            continue
        record = {
            "source_dataset": source_dataset,
            "source_split": source_split,
            "source_index": i,
            "raw_problem": raw_problem,
            **classification,
        }
        if dry_run:
            print(json.dumps(record, indent=2, ensure_ascii=False))
        else:
            collection.update_one(
                {
                    "source_dataset": source_dataset,
                    "source_split": source_split,
                    "source_index": i,
                },
                {"$set": record},
                upsert=True,
            )
            print(f"[Phase A] Stored classification for index {i}")
        time.sleep(0.2)


def process_phase_b(
    source_dataset: str,
    source_split: str,
    kc_tags: dict,
    max_samples: Optional[int],
    collection,
    dry_run: bool,
):
    """Run Phase B: generate statement, parameters, and answer."""
    cursor = collection.find({
        "source_dataset": source_dataset,
        "source_split": source_split,
        "statement": {"$exists": False},
        "kc": {"$exists": True},
    }).sort("source_index", 1)
    processed = 0
    for doc in cursor:
        if max_samples is not None and processed >= max_samples:
            break
        i = doc["source_index"]
        raw_problem = doc.get("raw_problem", "")
        classification = {
            "course": doc.get("course"),
            "kc": doc.get("kc"),
            "tags": doc.get("tags"),
            "difficulty": doc.get("difficulty"),
        }
        prompt = build_phase_b_prompt(raw_problem=raw_problem, classification=classification)
        try:
            output = ollama_chat(OLLAMA_MODELS["generator"], prompt, temperature=0.2)
            b_result = safe_json_extract(output)
        except Exception as e:
            print(f"[ERROR] Phase B failed at index {i}: {e}")
            continue
        update = {
            "statement": b_result.get("statement"),
            "parameters": b_result.get("parameters", {}),
            "answer": b_result.get("answer"),
        }
        if dry_run:
            print(json.dumps({**doc, **update}, indent=2, ensure_ascii=False))
        else:
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": update},
            )
            print(f"[Phase B] Stored statement/answer for index {i}")
        processed += 1
        time.sleep(0.2)


def process_phase_c(
    source_dataset: str,
    source_split: str,
    kc_tags: dict,
    taxonomy: str,
    max_samples: Optional[int],
    collection,
    validate: bool,
    validation_rate: float,
    no_semantic_check: bool,
    dry_run: bool,
):
    """Run Phase C: generate solution steps and optionally validate."""
    cursor = collection.find({
        "source_dataset": source_dataset,
        "source_split": source_split,
        "statement": {"$exists": True},
        "answer": {"$exists": True},
        "solution_steps": {"$exists": False},
    }).sort("source_index", 1)
    processed = 0
    import random as _random
    for doc in cursor:
        if max_samples is not None and processed >= max_samples:
            break
        i = doc["source_index"]
        raw_problem = doc.get("raw_problem", "")
        classification = {
            "course": doc.get("course"),
            "kc": doc.get("kc"),
            "tags": doc.get("tags"),
            "difficulty": doc.get("difficulty"),
        }
        statement = doc.get("statement")
        answer = doc.get("answer")
        parameters = doc.get("parameters", {})
        prompt = build_phase_c_prompt(
            raw_problem=raw_problem,
            classification=classification,
            statement=statement,
            answer=answer,
            parameters=parameters,
        )
        try:
            output = ollama_chat(OLLAMA_MODELS["generator"], prompt, temperature=0.2)
            c_result = safe_json_extract(output)
        except Exception as e:
            print(f"[ERROR] Phase C failed at index {i}: {e}")
            continue
        solution_steps = c_result.get("solution_steps", [])
        update = {"solution_steps": solution_steps}
        # Perform optional validation on a random subset
        if validate and validation_rate > 0 and _random.random() < validation_rate:
            ok, reason = validate_with_mathstral(
                {**doc, **update},
                kc_tags,
                taxonomy=taxonomy,
                semantic_check=(not no_semantic_check),
                return_reason=True,
            )
            if not ok:
                print(f"[SKIP] Validation failed for index {i}: {reason}")
                continue
        if dry_run:
            print(json.dumps({**doc, **update}, indent=2, ensure_ascii=False))
        else:
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": update},
            )
            print(f"[Phase C] Stored solution steps for index {i}")
        processed += 1
        time.sleep(0.2)


def run_pipeline(
    dataset: str,
    config: str | None,
    split: str,
    kc_tags_file: str,
    taxonomy_file: str,
    phase: str = "all",
    max_samples: int | None = None,
    validate: bool = False,
    validation_rate: float = 1.0,
    no_semantic_check: bool = False,
    dry_run: bool = False,
):
    kc_tags = load_json(kc_tags_file)
    taxonomy = load_text(taxonomy_file)

    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]

    ds = None
    if phase in ("A", "all"):
        ds = load_dataset(dataset, config, split=split)

    if phase in ("A", "all"):
        process_phase_a(
            ds=ds,
            source_dataset=dataset,
            source_split=split,
            kc_tags=kc_tags,
            taxonomy=taxonomy,
            max_samples=max_samples,
            collection=collection,
            dry_run=dry_run,
        )

    if phase in ("B", "all"):
        process_phase_b(
            source_dataset=dataset,
            source_split=split,
            kc_tags=kc_tags,
            max_samples=max_samples,
            collection=collection,
            dry_run=dry_run,
        )

    if phase in ("C", "all"):
        process_phase_c(
            source_dataset=dataset,
            source_split=split,
            kc_tags=kc_tags,
            taxonomy=taxonomy,
            max_samples=max_samples,
            collection=collection,
            validate=validate,
            validation_rate=validation_rate,
            no_semantic_check=no_semantic_check,
            dry_run=dry_run,
        )
