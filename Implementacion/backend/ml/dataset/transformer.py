#!/usr/bin/env python3
"""
transformer.py
==============

Offline dataset transformation pipeline.

- Loads math problems from a Hugging Face dataset (placeholder configurable).
- Uses Mathstral via Ollama (local) to transform problems into a structured JSON format.
- Enforces taxonomy and KC/tag consistency using kc_tags.json and taxonomy.in.
- Optionally validates mathematical correctness + semantic tag fit using Mathstral.
- Stores intermediate and final results in MongoDB (math_tutor.problems), so phases can be resumed.

This script is meant to be run occasionally, not as part of the live backend.
"""

import json
import random
import re
import time
import unicodedata
from typing import Dict, Any, List, Optional, Tuple

import requests
from pymongo import MongoClient
from datasets import load_dataset


# =========================
# CONFIGURATION
# =========================

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODELS = {
    "generator": "mathstral:latest",
    "validator": "mathstral:latest",
}

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "math_tutor"
COLLECTION_NAME = "problems"

ALLOWED_COURSES = {
    "1º ESO",
    "2º ESO",
    "3º ESO",
    "4º ESO",
    "1º Bach",
    "2º Bach",
}

COURSE_ALIASES = {
    "1 eso": "1º ESO",
    "2 eso": "2º ESO",
    "3 eso": "3º ESO",
    "4 eso": "4º ESO",
    "1 bach": "1º Bach",
    "1 bachillerato": "1º Bach",
    "2 bach": "2º Bach",
    "2 bachillerato": "2º Bach",
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


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def normalize_text(text: str) -> str:
    text = strip_accents(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=100)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def safe_json_extract(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start:end+1])


def instantiate_parameters(parameters: Dict[str, List[int]]) -> Dict[str, int]:
    inst = {}
    for k, v in parameters.items():
        if isinstance(v, list) and len(v) == 2:
            inst[k] = random.randint(v[0], v[1])
    return inst


# =========================
# TAXONOMY HELPERS
# =========================

def build_kc_indices(kc_tags: dict) -> tuple[dict, dict, dict]:
    kcs = kc_tags.get("kcs", {})
    normalized_kc_map = {normalize_text(kc): kc for kc in kcs.keys()}

    tag_to_kcs: dict[str, list[str]] = {}
    normalized_tag_map: dict[str, str] = {}
    for kc, kc_def in kcs.items():
        for tag in kc_def.get("maps_from_tags", []):
            tag = str(tag).strip()
            ntag = normalize_text(tag)
            normalized_tag_map[ntag] = tag
            tag_to_kcs.setdefault(tag, []).append(kc)
    return normalized_kc_map, normalized_tag_map, tag_to_kcs


def normalize_course_value(raw_course: Any) -> Optional[str]:
    if raw_course is None:
        return None
    raw = str(raw_course).strip()
    if raw in ALLOWED_COURSES:
        return raw
    nr = normalize_text(raw)
    if nr in COURSE_ALIASES:
        return COURSE_ALIASES[nr]
    return None


def keyword_overlap_score(text_norm: str, candidate: str) -> int:
    cand_norm = normalize_text(candidate)
    if not cand_norm:
        return 0
    if cand_norm in text_norm:
        return max(2, len(cand_norm.split()))
    score = 0
    for token in cand_norm.split():
        if len(token) >= 4 and token in text_norm:
            score += 1
    return score


def infer_kc_from_text(raw_problem: str, kc_tags: dict) -> Optional[str]:
    text_norm = normalize_text(raw_problem)
    best_kc = None
    best_score = 0
    for kc, kc_def in kc_tags.get("kcs", {}).items():
        score = keyword_overlap_score(text_norm, kc_def.get("description", ""))
        for tag in kc_def.get("maps_from_tags", []):
            score += keyword_overlap_score(text_norm, str(tag))
        if score > best_score:
            best_score = score
            best_kc = kc
    return best_kc if best_score > 0 else None


def infer_tags_for_kc(raw_problem: str, kc: str, kc_tags: dict, max_tags: int = 3) -> list[str]:
    text_norm = normalize_text(raw_problem)
    allowed = kc_tags.get("kcs", {}).get(kc, {}).get("maps_from_tags", [])
    scored: list[tuple[int, str]] = []
    for tag in allowed:
        score = keyword_overlap_score(text_norm, str(tag))
        if score > 0:
            scored.append((score, str(tag)))
    scored.sort(key=lambda x: (-x[0], x[1]))
    tags = [tag for _, tag in scored[:max_tags]]
    if tags:
        return tags

    # Fallback: choose a generic / umbrella tag if present, else the first allowed tag.
    for tag in allowed:
        tag_s = str(tag)
        if "(" not in tag_s and len(tag_s.split()) <= 4:
            return [tag_s]
    return [str(allowed[0])] if allowed else []


def repair_phase_a_classification(raw_problem: str, classification: dict, kc_tags: dict) -> tuple[Optional[dict], list[str]]:
    notes: list[str] = []
    kcs = kc_tags.get("kcs", {})
    normalized_kc_map, normalized_tag_map, tag_to_kcs = build_kc_indices(kc_tags)

    course = normalize_course_value(classification.get("course"))
    if course is None:
        notes.append("invalid_course")

    raw_kc = str(classification.get("kc", "")).strip()
    kc = raw_kc if raw_kc in kcs else None

    if kc is None and raw_kc:
        nkc = normalize_text(raw_kc)
        kc = normalized_kc_map.get(nkc)
        if kc:
            notes.append("kc_normalized")

    if kc is None and raw_kc:
        possible_tag = normalized_tag_map.get(normalize_text(raw_kc))
        if possible_tag:
            possible_kcs = tag_to_kcs.get(possible_tag, [])
            if len(possible_kcs) == 1:
                kc = possible_kcs[0]
                notes.append("kc_recovered_from_tag")

    raw_tags = classification.get("tags", [])
    if not isinstance(raw_tags, list):
        raw_tags = [raw_tags]

    tags: list[str] = []
    for t in raw_tags:
        ts = str(t).strip()
        if not ts:
            continue
        if ts in normalized_tag_map.values():
            tags.append(ts)
            continue
        maybe_tag = normalized_tag_map.get(normalize_text(ts))
        if maybe_tag:
            tags.append(maybe_tag)

    tags = list(dict.fromkeys(tags))

    if kc is None and tags:
        candidate_counts: dict[str, int] = {}
        for tag in tags:
            for candidate_kc in tag_to_kcs.get(tag, []):
                candidate_counts[candidate_kc] = candidate_counts.get(candidate_kc, 0) + 1
        if candidate_counts:
            kc = max(candidate_counts.items(), key=lambda kv: kv[1])[0]
            notes.append("kc_recovered_from_tags")

    if kc is None:
        inferred_kc = infer_kc_from_text(raw_problem, kc_tags)
        if inferred_kc is not None:
            kc = inferred_kc
            notes.append("kc_inferred_from_text")

    if kc is None:
        return None, notes + ["unresolved_kc"]

    allowed_for_kc = set(str(t).strip() for t in kcs[kc].get("maps_from_tags", []))
    tags = [t for t in tags if t in allowed_for_kc]

    if not tags:
        tags = infer_tags_for_kc(raw_problem, kc, kc_tags)
        notes.append("tags_inferred_from_text")

    difficulty = classification.get("difficulty", 3)
    try:
        difficulty = int(round(float(difficulty)))
    except Exception:
        difficulty = 3
        notes.append("difficulty_defaulted")
    difficulty = max(1, min(5, difficulty))

    repaired = {
        "course": course or "3º ESO",
        "kc": kc,
        "tags": tags,
        "difficulty": difficulty,
    }
    return repaired, notes


def phase_a_record_is_valid(record: dict, kc_tags: dict) -> tuple[bool, str]:
    course = str(record.get("course", "")).strip()
    if course not in ALLOWED_COURSES:
        return False, "invalid course"

    kc = str(record.get("kc", "")).strip()
    kcs = kc_tags.get("kcs", {})
    if kc not in kcs:
        return False, "invalid kc"

    tags = record.get("tags", [])
    if not isinstance(tags, list) or not tags:
        return False, "invalid tags"

    allowed = set(str(t).strip() for t in kcs[kc].get("maps_from_tags", []))
    if any(str(t).strip() not in allowed for t in tags):
        return False, "tags not allowed for kc"

    difficulty = record.get("difficulty")
    if not isinstance(difficulty, int) or not (1 <= difficulty <= 5):
        return False, "invalid difficulty"

    return True, "ok"


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
    kc_examples = []
    for kc, kc_def in list(kc_tags.get("kcs", {}).items())[:20]:
        sample_tags = kc_def.get("maps_from_tags", [])[:5]
        kc_examples.append(f"- {kc}: {sample_tags}")

    return f"""
You are classifying a math problem for a Spanish secondary-school tutoring dataset.

IMPORTANT RULES:
- "kc" must be EXACTLY ONE key from kc_tags["kcs"], such as "Algebra.LinearEquations" or "Proportionality.Percentages".
- "kc" is NOT a human-readable topic and is NOT one of the tags.
- "tags" must be chosen ONLY from the allowed tags of the selected kc.
- Do NOT invent tags from names, numbers, people, months, or entities appearing in the statement.
- Return 1 to 3 tags maximum.
- Output ONLY JSON.

Required JSON schema:
{{
  "course": "one allowed course",
  "kc": "one exact kc key",
  "tags": ["tag1", "tag2"],
  "difficulty": 1
}}

Allowed courses:
{sorted(ALLOWED_COURSES)}

Examples of valid kc -> tags:
{chr(10).join(kc_examples)}

Taxonomy excerpt:
{taxonomy[:4000]}

Raw problem:
{raw_problem}

Source dataset: {source_dataset}
Source split: {source_split}
Source index: {source_index}

Return ONLY valid JSON.
"""


def build_phase_b_prompt(raw_problem: str, classification: dict) -> str:
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

CLASSIFICATION
course: {course}
kc: {kc}
tags: {tags}
difficulty: {difficulty}

RAW PROBLEM
{raw_problem}

Return a JSON object with keys "statement", "parameters", and "answer" exactly.
Use only valid JSON.
"""


def build_phase_c_prompt(raw_problem: str, classification: dict, statement: str, answer: str, parameters: dict) -> str:
    course = classification.get("course", "")
    kc = classification.get("kc", "")
    tags = classification.get("tags", [])
    difficulty = classification.get("difficulty", "")
    return f"""
You are a math tutor writing step-by-step solution for a Spanish high-school math problem.

CONTEXT
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

Return a JSON object with key "solution_steps" containing an array of Spanish sentences.
Each sentence should be clear and reflect a logical step towards obtaining the final answer.
Use the parameter names in your reasoning where appropriate.
Output ONLY valid JSON.
"""


def build_phase_c_repair_prompt(
    statement: str,
    parameters: dict,
    answer: str,
    solution_steps: list[str],
) -> str:
    return f"""
You are repairing a structured math problem record.

The current record may contain an incorrect final answer and/or incorrect solution steps.
Your task is to produce a corrected final answer and corrected solution steps that are mathematically consistent with the statement.

STATEMENT:
{statement}

PARAMETERS:
{json.dumps(parameters, ensure_ascii=False)}

CURRENT ANSWER:
{answer}

CURRENT SOLUTION STEPS:
{json.dumps(solution_steps, ensure_ascii=False)}

Return ONLY valid JSON with this schema:
{{
  "answer": "correct final answer",
  "solution_steps": ["step 1", "step 2", "step 3"],
  "changed": true
}}

Rules:
- If the current answer is wrong, replace it with the mathematically correct answer.
- If the current solution steps are wrong or inconsistent, replace them.
- If everything is already correct, return the same answer/steps and "changed": false.
- Output ONLY JSON.
"""


def try_repair_phase_c_record(doc: dict) -> tuple[Optional[dict], Optional[str]]:
    prompt = build_phase_c_repair_prompt(
        statement=doc.get("statement", ""),
        parameters=doc.get("parameters", {}),
        answer=doc.get("answer", ""),
        solution_steps=doc.get("solution_steps", []),
    )

    try:
        output = ollama_chat(OLLAMA_MODELS["generator"], prompt, temperature=0.0)
        repaired = safe_json_extract(output)
        return repaired, None
    except Exception as e:
        return None, str(e)


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
    def fail(msg: str):
        return (False, msg) if return_reason else False

    required_fields = ["course", "kc", "tags", "statement", "solution_steps", "answer"]
    for f in required_fields:
        if f not in problem:
            return fail(f"Missing required field: {f}")

    if not isinstance(problem["tags"], list):
        return fail("Field 'tags' must be a list.")
    if not isinstance(problem["solution_steps"], list):
        return fail("Field 'solution_steps' must be a list.")

    course = str(problem.get("course", "")).strip()
    if course not in ALLOWED_COURSES:
        return fail(f"Invalid course '{course}'. Must be one of: {sorted(ALLOWED_COURSES)}")

    kc = str(problem.get("kc", "")).strip()
    kcs = kc_tags.get("kcs", {})
    if kc not in kcs:
        return fail(f"KC '{kc}' not found in kc_tags.json")

    global_vocab = set()
    for kc_def in kcs.values():
        for t in kc_def.get("maps_from_tags", []):
            global_vocab.add(str(t).strip())

    tags = [str(t).strip() for t in problem.get("tags", []) if str(t).strip()]
    unknown_tags = [t for t in tags if t not in global_vocab]
    if unknown_tags:
        return fail(f"Unknown tags not in kc_tags.json vocabulary: {unknown_tags}")

    allowed_for_kc = set(str(t).strip() for t in kcs[kc].get("maps_from_tags", []))
    not_in_kc = [t for t in tags if t not in allowed_for_kc]
    if not_in_kc:
        return fail(
            f"Tags not allowed for KC '{kc}': {not_in_kc}. "
            f"Allowed tags for this KC are: {sorted(allowed_for_kc)}"
        )

    if not semantic_check:
        return (True, "OK (hard validation only)") if return_reason else True

    taxonomy_excerpt = taxonomy[:1200] if taxonomy else ""
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
# PHASE PROCESSORS
# =========================

def process_phase_a(
    ds,
    source_dataset: str,
    source_split: str,
    source_config: str | None,
    kc_tags: dict,
    taxonomy: str,
    max_samples: Optional[int],
    collection,
    dry_run: bool,
):
    """Run Phase A: classify the next unprocessed problems into course/kc/tags/difficulty."""

    processed = 0
    attempted = 0

    for i, ex in enumerate(ds):
        if max_samples is not None and attempted >= max_samples:
            break

        attempted += 1
        # Skip problems already present in Mongo for this dataset/config/split/index
        existing = collection.find_one(
            {
                "source_dataset": source_dataset,
                "source_config": source_config,
                "source_split": source_split,
                "source_index": i,
                "pipeline.phase_A.status": "done",
            },
            {"_id": 1},
        )
        if existing is not None:
            continue

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

        repaired, repair_notes = repair_phase_a_classification(raw_problem, classification, kc_tags)

        if repaired is None:
            if not dry_run:
                collection.update_one(
                    {
                        "source_dataset": source_dataset,
                        "source_config": source_config,
                        "source_split": source_split,
                        "source_index": i,
                    },
                    {
                        "$set": {
                            "source_dataset": source_dataset,
                            "source_config": source_config,
                            "source_split": source_split,
                            "source_index": i,
                            "raw_problem": raw_problem,
                            "pipeline.phase_A": {
                                "status": "error",
                                "error": "Could not repair invalid classification",
                                "repair_notes": repair_notes,
                                "model": OLLAMA_MODELS["generator"],
                                "updated_at": time.time(),
                            },
                        }
                    },
                    upsert=True,
                )
            print(f"[ERROR] Phase A failed at index {i}: could not repair classification")
            continue

        is_valid, reason = phase_a_record_is_valid(repaired, kc_tags)
        if not is_valid:
            if not dry_run:
                collection.update_one(
                    {
                        "source_dataset": source_dataset,
                        "source_config": source_config,
                        "source_split": source_split,
                        "source_index": i,
                    },
                    {
                        "$set": {
                            "source_dataset": source_dataset,
                            "source_config": source_config,
                            "source_split": source_split,
                            "source_index": i,
                            "raw_problem": raw_problem,
                            **repaired,
                            "pipeline.phase_A": {
                                "status": "error",
                                "error": reason,
                                "repair_notes": repair_notes,
                                "model": OLLAMA_MODELS["generator"],
                                "updated_at": time.time(),
                            },
                        }
                    },
                    upsert=True,
                )
            print(f"[ERROR] Phase A invalid at index {i}: {reason}")
            continue

        record = {
            "source_dataset": source_dataset,
            "source_config": source_config,
            "source_split": source_split,
            "source_index": i,
            "raw_problem": raw_problem,
            **repaired,
            "pipeline.phase_A": {
                "status": "done",
                "model": OLLAMA_MODELS["generator"],
                "repair_notes": repair_notes,
                "updated_at": time.time(),
            },
        }

        if dry_run:
            print(json.dumps(record, indent=2, ensure_ascii=False))
        else:
            collection.update_one(
                {
                    "source_dataset": source_dataset,
                    "source_config": source_config,
                    "source_split": source_split,
                    "source_index": i,
                },
                {"$set": record},
                upsert=True,
            )
            print(f"[Phase A] Stored classification for index {i}")

        processed += 1
        time.sleep(0.2)

    print(f"[Phase A] Processed {processed} new problems")


def process_phase_b(
    source_dataset: str,
    source_config: str,
    source_split: str,
    kc_tags: dict,
    max_samples: Optional[int],
    collection,
    dry_run: bool,
):
    """
    Run Phase B: generate statement, parameters, and answer.

    Pending items for Phase B are:
    - phase_A done
    - phase_B missing OR phase_B == error

    Items already marked done/modified are skipped.
    """

    cursor = collection.find({
        "source_dataset": source_dataset,
        "source_config": source_config,
        "source_split": source_split,
        "pipeline.phase_A.status": "done",
        "$or": [
            {"pipeline.phase_B.status": {"$exists": False}},
            {"pipeline.phase_B.status": "error"},
        ],
        "kc": {"$exists": True, "$ne": None},
        "raw_problem": {"$exists": True, "$ne": None},
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

        prompt = build_phase_b_prompt(
            raw_problem=raw_problem,
            classification=classification,
        )

        try:
            output = ollama_chat(
                OLLAMA_MODELS["generator"],
                prompt,
                temperature=0.2,
            )
            b_result = safe_json_extract(output)
        except Exception as e:
            if not dry_run:
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "pipeline.phase_B": {
                            "status": "error",
                            "error": str(e),
                            "updated_at": time.time(),
                        }
                    }},
                )
            print(f"[ERROR] Phase B failed at index {i}: {e}")
            continue

        # Defensive normalization
        statement = b_result.get("statement")
        answer = b_result.get("answer")
        parameters = b_result.get("parameters", {})

        if statement is not None:
            statement = str(statement).strip()
        if answer is not None:
            answer = str(answer).strip()

        if not isinstance(parameters, dict):
            parameters = {}

        # Basic output validation
        errors = []
        if not statement:
            errors.append("missing_or_empty_statement")
        if answer is None or answer == "":
            errors.append("missing_or_empty_answer")

        if errors:
            if not dry_run:
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "pipeline.phase_B": {
                            "status": "error",
                            "error": f"Invalid Phase B output: {', '.join(errors)}",
                            "raw_model_output": output[:4000],
                            "updated_at": time.time(),
                        }
                    }},
                )
            print(f"[ERROR] Phase B invalid output at index {i}: {', '.join(errors)}")
            continue

        update = {
            "statement": statement,
            "parameters": parameters,
            "answer": answer,
            "pipeline.phase_B": {
                "status": "done",
                "model": OLLAMA_MODELS["generator"],
                "updated_at": time.time(),
            },
        }

        if dry_run:
            print(json.dumps({**doc, **update}, indent=2, ensure_ascii=False))
        else:
            collection.update_one({"_id": doc["_id"]}, {"$set": update})
            print(f"[Phase B] Stored statement/answer for index {i}")

        processed += 1
        time.sleep(0.2)

    print(f"[Phase B] Processed {processed} problems")


def process_phase_c(
    source_dataset: str,
    source_config: str,
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
    cursor = collection.find({
        "source_dataset": source_dataset,
        "source_config": source_config,
        "source_split": source_split,
        "pipeline.phase_A.status": "done",
        "pipeline.phase_B.status": "done",
        "$or": [
            {"pipeline.phase_C.status": {"$exists": False}},
            {"pipeline.phase_C.status": "error"},
            {"pipeline.phase_C.status": "modified"},
        ],
        "statement": {"$exists": True, "$ne": None},
        "answer": {"$exists": True, "$ne": None},
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
            if not dry_run:
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "pipeline.phase_C": {
                            "status": "error",
                            "error": str(e),
                            "updated_at": time.time(),
                        }
                    }},
                )
            print(f"[ERROR] Phase C failed at index {i}: {e}")
            continue

        solution_steps = c_result.get("solution_steps", [])
        if not isinstance(solution_steps, list):
            solution_steps = []

        # Default outcome for a successful generation
        phase_c_update = {
            "solution_steps": solution_steps,
            "pipeline.phase_C": {
                "status": "done",
                "model": OLLAMA_MODELS["generator"],
                "updated_at": time.time(),
            },
        }

        # Optional validation
        should_validate = (
            validate and validation_rate > 0 and _random.random() < validation_rate
        )

        if should_validate:
            ok, reason = validate_with_mathstral(
                {**doc, **phase_c_update},
                kc_tags,
                taxonomy=taxonomy,
                semantic_check=(not no_semantic_check),
                return_reason=True,
            )

            if not ok:
                if not dry_run:
                    collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {
                            "pipeline.phase_C": {
                                "status": "validation_failed",
                                "error": reason,
                                "updated_at": time.time(),
                            }
                        }},
                    )
                print(f"[SKIP] Validation failed for index {i}: {reason}")
                continue

        # Successful path: always save
        if dry_run:
            print(json.dumps({**doc, **phase_c_update}, indent=2, ensure_ascii=False))
        else:
            collection.update_one({"_id": doc["_id"]}, {"$set": phase_c_update})
            print(f"[Phase C] Stored solution steps for index {i}")

        processed += 1
        time.sleep(0.2)


# =========================
# MAIN PIPELINE
# =========================

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
    desired_index_keys = [
        ("source_dataset", 1),
        ("source_config", 1),
        ("source_split", 1),
        ("source_index", 1),
    ]
    desired_index_name = "source_identity_unique"

    existing_indexes = collection.index_information()

    if desired_index_name in existing_indexes:
        existing_keys = existing_indexes[desired_index_name]["key"]
        if existing_keys != desired_index_keys:
            print(f"[INFO] Dropping outdated index '{desired_index_name}'")
            collection.drop_index(desired_index_name)

    collection.create_index(
        desired_index_keys,
        unique=True,
        name=desired_index_name,
    )

    ds = None
    if phase in ("A", "all"):
        ds = load_dataset(dataset, config, split=split)

    if phase in ("A", "all"):
        process_phase_a(
            ds=ds,
            source_dataset=dataset,
            source_split=split,
            source_config=config,
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
            source_config=config,
            kc_tags=kc_tags,
            max_samples=max_samples,
            collection=collection,
            dry_run=dry_run,
        )

    if phase in ("C", "all"):
        process_phase_c(
            source_dataset=dataset,
            source_split=split,
            source_config=config,
            kc_tags=kc_tags,
            taxonomy=taxonomy,
            max_samples=max_samples,
            collection=collection,
            validate=validate,
            validation_rate=validation_rate,
            no_semantic_check=no_semantic_check,
            dry_run=dry_run,
        )
