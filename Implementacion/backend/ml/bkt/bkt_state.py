"""
ml/bkt/bkt_state.py
-------------------
Pure Bayesian Knowledge Tracing mathematics.

No database access, no FastAPI, no side-effects.
Every function here is a deterministic computation over plain Python values.

Theory
------
BKT treats each Knowledge Component (KC) as a hidden binary variable:
the student either *knows* it (L=1) or not (L=0). We never observe this
directly — only whether they answered correctly or not. Four parameters
govern the model:

  P(L0) — prior probability of already knowing the KC
  P(T)  — probability of learning the KC after one attempt  (transition)
  P(S)  — probability of slipping (wrong answer despite knowing)
  P(G)  — probability of guessing  (right answer despite not knowing)

The student state for a KC is a single scalar p_know ∈ [0, 1].
It is updated in two steps after each observed answer:

  Step 1 — Evidence update (what does this answer tell us?):

      correct:   P(L|correct)   = P(L)·(1-S) / [ P(L)·(1-S) + (1-P(L))·G ]
      incorrect: P(L|incorrect) = P(L)·S     / [ P(L)·S     + (1-P(L))·(1-G) ]

  Step 2 — Learning update (they may have learned from the attempt):

      P(L_new) = P(L|evidence) + (1 - P(L|evidence)) · P(T)

Default parameter values follow the ITS literature (Corbett & Anderson 1994).
They are intentionally conservative and should be tuned per-KC once enough
data is available (see scripts/train_bkt.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Default global BKT parameters
# ---------------------------------------------------------------------------

DEFAULT_P_KNOW_INIT: float = 0.20   # pessimistic prior — assume the student doesn't know yet
DEFAULT_P_LEARN: float = 0.15       # moderate learning rate per attempt
DEFAULT_P_SLIP: float = 0.10        # low slip rate (rarely wrong when you know)
DEFAULT_P_GUESS: float = 0.20       # modest guess rate
DEFAULT_MASTERY_THRESHOLD: float = 0.90  # p_know >= this → KC considered mastered


@dataclass(frozen=True)
class KCParams:
    """
    BKT parameters for a single Knowledge Component.

    These are KC-level constants, not per-student. They describe the
    nature of the KC itself (how hard is it to learn, how guessable is it).

    Start with the global defaults. Once you have enough attempt data per KC
    you can fit them with scripts/train_bkt.py and store them in the
    `kc_params` collection, then load them in bkt_runtime.py.
    """
    p_know_init: float = DEFAULT_P_KNOW_INIT
    p_learn: float = DEFAULT_P_LEARN
    p_slip: float = DEFAULT_P_SLIP
    p_guess: float = DEFAULT_P_GUESS
    mastery_threshold: float = DEFAULT_MASTERY_THRESHOLD


# Singleton used everywhere until per-KC params are fitted
GLOBAL_KC_PARAMS = KCParams()


# ---------------------------------------------------------------------------
# Core BKT update
# ---------------------------------------------------------------------------

def bkt_update(
    p_know: float,
    is_correct: bool,
    params: KCParams = GLOBAL_KC_PARAMS,
) -> float:
    """
    Run one BKT step given a single observation.

    Parameters
    ----------
    p_know     : current probability of knowing the KC  (before this attempt)
    is_correct : True if the student answered correctly
    params     : BKT parameters for this KC

    Returns
    -------
    Updated p_know after incorporating the observation.
    """
    p = float(p_know)

    # --- Step 1: evidence update ---
    if is_correct:
        numer = p * (1.0 - params.p_slip)
        denom = numer + (1.0 - p) * params.p_guess
    else:
        numer = p * params.p_slip
        denom = numer + (1.0 - p) * (1.0 - params.p_guess)

    p_given_obs = (numer / denom) if denom > 1e-12 else p

    # --- Step 2: learning update ---
    p_new = p_given_obs + (1.0 - p_given_obs) * params.p_learn

    return float(min(max(p_new, 0.0), 1.0))


# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------

def is_mastered(p_know: float, params: KCParams = GLOBAL_KC_PARAMS) -> bool:
    """Return True when p_know crosses the mastery threshold."""
    return float(p_know) >= params.mastery_threshold


def cold_start_p_know(interest_score: Optional[float]) -> float:
    """
    Map a questionnaire interest score (1–5) to an initial p_know.

    Rationale: a student who rates a KC 5/5 likely has prior exposure,
    so we start with a higher knowledge estimate than the uninformed prior.
    A student who rates it 1/5 probably has little background.

    Mapping:
      score 1 → p_know 0.10
      score 3 → p_know 0.20  (same as global default)
      score 5 → p_know 0.40

    This is used only when no BKT history exists for a KC (cold start).
    It is intentionally conservative to avoid overestimating prior knowledge.
    """
    if interest_score is None:
        return DEFAULT_P_KNOW_INIT
    normalized = (float(interest_score) - 1.0) / 4.0   # 0.0 … 1.0
    return round(0.10 + 0.30 * normalized, 4)           # 0.10 … 0.40