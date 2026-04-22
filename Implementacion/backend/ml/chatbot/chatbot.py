# backend/ml/chatbot/chatbot.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

import requests


CHATBOT_OLLAMA_URL = os.environ.get("CHATBOT_OLLAMA_URL", os.environ.get("OLLAMA_URL", "http://localhost:11434"))
CHATBOT_MODEL = os.environ.get("CHATBOT_MODEL", "deepseek-r1:latest")

# Practical runtime defaults (you can tune)
CHATBOT_TIMEOUT = float(os.environ.get("CHATBOT_TIMEOUT_SECS", "120"))  # keep it responsive at runtime
CHATBOT_NUM_PREDICT = int(os.environ.get("CHATBOT_NUM_PREDICT", "400"))  # cap output tokens


def _ollama_chat(prompt: str, temperature: float = 0.2) -> str:
    payload = {
        "model": CHATBOT_MODEL,
        "messages": [
            {"role": "system", "content": "Eres un tutor de matemáticas. Responde en español, claro y conciso."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": temperature,
            "num_predict": CHATBOT_NUM_PREDICT,
        },
    }
    r = requests.post(f"{CHATBOT_OLLAMA_URL}/api/chat", json=payload, timeout=CHATBOT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return (data.get("message", {}) or {}).get("content", "").strip()


def _build_prompt(
    statement: str,
    solution_steps: List[str],
    final_answer: str,
    student_question: str,
    current_attempt: Optional[str] = None,
) -> str:
    # Keep steps short in prompt to reduce latency; include only first N steps.
    steps = solution_steps[:6] if solution_steps else []
    steps_text = "\n".join(f"- {s}" for s in steps)

    attempt_block = ""
    if current_attempt:
        attempt_block = f"\n\nIntento actual del alumno:\n{current_attempt}\n"

    return f"""Contexto del problema:
Enunciado:
{statement}

Pasos (resumen):
{steps_text if steps_text else "(no disponible)"}

Respuesta final (para referencia interna):
{final_answer}

{attempt_block}
Pregunta del alumno:
{student_question}

Instrucciones:
- Responde en español, con claridad y brevedad.
- No des la respuesta final directamente a menos que el alumno lo pida explícitamente.
- Si el alumno está atascado, da una pista o explica el paso relevante.
"""


def generate_tutor_answer(problem: Dict[str, Any], student_question: str, rendered_statement, current_attempt: Optional[str] = None) -> str:
    statement = rendered_statement or str(problem.get("statement", "")).strip()
    steps = problem.get("solution_steps") or []
    answer = str(problem.get("answer", "")).strip()

    if not statement:
        # If dataset entry is incomplete, still answer but warn
        statement = "(Enunciado no disponible. El alumno pregunta sobre un problema sin enunciado almacenado.)"

    prompt = _build_prompt(
        statement=statement,
        solution_steps=steps,
        final_answer=answer,
        student_question=student_question,
        current_attempt=current_attempt,
    )
    return _ollama_chat(prompt, temperature=0.2)
