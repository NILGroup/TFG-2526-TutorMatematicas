"""
ml/bkt/heuristic.py
--------------------
Heuristic + BKT recommendation model.

Architecture
------------
The KC score formula is:

    score(kc) = Wi·Ikc + Wn·Nkc + Wu·Ukc + Wd·Dkc - Precent - Prepeat

Where:
  Ikc   = normalized questionnaire interest          (from user preferences)
  Nkc   = learning need                              (from BKT when available, else from accuracy)
  Ukc   = uncertainty — high when attempts are few   (always from attempt count)
  Dkc   = diversity bonus — higher if not in session (session shape)
  Wi…Wd = weights determined by the user's primary objective

BKT Integration
---------------
The only change BKT makes to this formula is how Nkc is computed:

  Without BKT: Nkc = 1 − smoothed_accuracy(attempts)
  With BKT:    Nkc = 1 − p_know(kc)   from bkt_state

This is a clean substitution. BKT produces a more principled estimate of
"how much does this student still need to learn this KC?" which is exactly
what Nkc represents. Everything else — interest, uncertainty, diversity,
penalties, fuzzy difficulty, course selection — is unchanged.

When a KC is marked as mastered (p_know ≥ threshold), its need collapses
to zero, which combined with the normal diversity/penalty logic means it
naturally drops out of recommendations without any special-casing.

Uncertainty (Ukc) is intentionally kept independent of BKT. It captures
how reliable our estimates are in general and discourages ignoring KCs
that haven't been seen enough times for BKT to settle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np

DEFAULT_SCORE = 3.0


@dataclass
class HeuristicConfig:
    default_kc_score: float = DEFAULT_SCORE
    default_tag_score: float = DEFAULT_SCORE
    course_order: List[str] = field(default_factory=lambda: [
        "1º ESO", "2º ESO", "3º ESO", "4º ESO", "1º Bach", "2º Bach"
    ])
    prior_accuracy: float = 0.65
    prior_weight: float = 2.0
    uncertainty_tau: float = 4.0
    recent_window: int = 4
    repetition_limit_per_kc: int = 2
    repetition_limit_per_tag: int = 2
    softmax_temperature: float = 0.35
    difficulty_sigma: float = 0.85
    default_avg_seconds: float = 90.0
    alpha_cross_course: float = 0.20
    # BKT: mastered KCs get this fixed need score (effectively silences them)
    bkt_mastered_need: float = 0.0
    objective_profiles: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "PRACTICE":         {"interest": 0.30, "need": 0.35, "uncertainty": 0.20, "diversity": 0.15},
        "IMPROVE_GRADES":   {"interest": 0.15, "need": 0.55, "uncertainty": 0.20, "diversity": 0.10},
        "REVIEW":           {"interest": 0.30, "need": 0.25, "uncertainty": 0.10, "diversity": 0.35},
        "LEARN_NEW_CONTENT":{"interest": 0.20, "need": 0.15, "uncertainty": 0.45, "diversity": 0.20},
    })


class HeuristicModel:
    COURSE_ALIASES: Dict[str, str] = {
        "1ESO": "1º ESO",
        "2ESO": "2º ESO",
        "3ESO": "3º ESO",
        "4ESO": "4º ESO",
        "1BACH": "1º Bach",
        "2BACH": "2º Bach",
    }

    def __init__(
        self,
        course_level: str,
        allow_cross_course: bool,
        kc_scores: Dict[str, float],
        tag_scores: Dict[str, Any],
        taxonomy: Dict[str, List[str]],
        min_difficulty: int,
        max_difficulty: int,
        target_difficulty: Optional[int] = None,
        config: Optional[HeuristicConfig] = None,
        seed: Optional[int] = None,
        performance_state: Optional[Dict[str, Any]] = None,
        primary_objective: str = "PRACTICE",
        # ----------------------------------------------------------------
        # BKT integration: map of kc → {"p_know": float, "mastered": bool}
        # When provided, Nkc = 1 - p_know instead of 1 - smoothed_accuracy.
        # When None or empty, falls back to the heuristic accuracy estimate.
        # ----------------------------------------------------------------
        bkt_state: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or HeuristicConfig()
        self.rng = np.random.default_rng(seed)

        self.course_level = self._normalize_course_label(course_level)
        self.allow_cross_course = bool(allow_cross_course)
        self.kc_scores = kc_scores or {}
        self.tag_scores = tag_scores or {}
        self.taxonomy = taxonomy or {}
        self.min_difficulty = int(min_difficulty)
        self.max_difficulty = int(max_difficulty)
        self.performance_state = performance_state or {}
        self.primary_objective = primary_objective or "PRACTICE"
        self.profile_target_difficulty = (
            int(target_difficulty)
            if target_difficulty is not None
            else int(round((self.min_difficulty + self.max_difficulty) / 2))
        )
        # BKT state: kc → {"p_know": float, "mastered": bool, "attempts": int}
        self.bkt_state: Dict[str, Any] = bkt_state or {}

        self._validate_inputs()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _normalize_course_label(self, label: str) -> str:
        return self.COURSE_ALIASES.get(label, label)

    def _validate_inputs(self) -> None:
        if self.course_level not in self.config.course_order:
            raise ValueError(f"Invalid course_level: {self.course_level}")
        if not isinstance(self.taxonomy, dict) or not self.taxonomy:
            raise ValueError("taxonomy must be a non-empty dict: {kc: [tag1, tag2, ...]}")
        if self.min_difficulty > self.max_difficulty:
            raise ValueError("min_difficulty cannot be greater than max_difficulty")
        if self.min_difficulty < 1 or self.max_difficulty < 1:
            raise ValueError("difficulty bounds must be >= 1")
        if not (0.0 <= self.config.alpha_cross_course <= 1.0):
            raise ValueError("alpha_cross_course must be in [0, 1]")
        if self.primary_objective not in self.config.objective_profiles:
            self.primary_objective = "PRACTICE"

    # ------------------------------------------------------------------
    # Math helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clip01(x: float) -> float:
        return float(np.clip(x, 0.0, 1.0))

    @staticmethod
    def _tri(x: float, a: float, b: float, c: float) -> float:
        if x <= a or x >= c:
            return 0.0
        if x == b:
            return 1.0
        if x < b:
            return (x - a) / (b - a)
        return (c - x) / (c - b)

    @staticmethod
    def _trap(x: float, a: float, b: float, c: float, d: float) -> float:
        if x <= a or x >= d:
            return 0.0
        if b <= x <= c:
            return 1.0
        if a < x < b:
            return (x - a) / (b - a)
        return (d - x) / (d - c)

    def _normalize_preference(self, score: Optional[float], default: float) -> float:
        raw = default if score is None else float(score)
        return self._clip01((raw - 1.0) / 4.0)

    def _safe_stats(self, stats: Optional[Dict[str, Any]]) -> Dict[str, float]:
        if not isinstance(stats, dict):
            return {"attempts": 0.0, "correct": 0.0, "avg_seconds": self.config.default_avg_seconds}
        return {
            "attempts": float(stats.get("attempts", 0.0) or 0.0),
            "correct": float(stats.get("correct", 0.0) or 0.0),
            "avg_seconds": float(stats.get("avg_seconds", self.config.default_avg_seconds) or self.config.default_avg_seconds),
        }

    def _smoothed_accuracy(self, stats: Optional[Dict[str, Any]]) -> float:
        s = self._safe_stats(stats)
        attempts = s["attempts"]
        correct = s["correct"]
        return (correct + self.config.prior_accuracy * self.config.prior_weight) / (attempts + self.config.prior_weight)

    def _uncertainty(self, stats: Optional[Dict[str, Any]]) -> float:
        s = self._safe_stats(stats)
        attempts = s["attempts"]
        return 1.0 / (1.0 + attempts / self.config.uncertainty_tau)

    def _need(self, stats: Optional[Dict[str, Any]]) -> float:
        """Heuristic-only need: 1 − smoothed accuracy. Used as fallback."""
        return 1.0 - self._smoothed_accuracy(stats)

    def _need_for_kc(self, kc: str, stats: Optional[Dict[str, Any]]) -> float:
        """
        Learning need for a KC — the Nkc component of the score formula.

        When BKT state is available for this KC:
            Nkc = 1 - p_know         (BKT estimate, more principled)
            Mastered KCs → Nkc = bkt_mastered_need ≈ 0

        When BKT state is not available (cold start, KC never attempted):
            Nkc = 1 - smoothed_accuracy  (heuristic fallback)
        """
        kc_bkt = self.bkt_state.get(kc)
        if kc_bkt is not None:
            if kc_bkt.get("mastered", False):
                return self.config.bkt_mastered_need
            return self._clip01(1.0 - float(kc_bkt.get("p_know", 0.20)))
        # Fallback: no BKT data for this KC yet
        return self._need(stats)

    def _recent_count(self, items: Optional[List[Any]], value: Any) -> int:
        if not items:
            return 0
        window = items[-self.config.recent_window:]
        return sum(1 for x in window if x == value)

    def _session_penalty(self, current_count: int, repetition_limit: int) -> float:
        if current_count <= 0:
            return 0.0
        if current_count < repetition_limit:
            return 0.15 * current_count
        return 0.15 * repetition_limit + 0.45 * (current_count - repetition_limit + 1)

    def _weighted_choice(self, weight_map: Dict[Any, float]) -> Any:
        if not weight_map:
            raise ValueError("Cannot sample from an empty weight map")
        items = list(weight_map.keys())
        weights = np.array([max(float(w), 1e-8) for w in weight_map.values()], dtype=float)
        temperature = max(self.config.softmax_temperature, 1e-3)
        logits = np.log(weights)
        logits = logits / temperature
        logits = logits - np.max(logits)
        probs = np.exp(logits)
        probs /= probs.sum()
        return self.rng.choice(items, p=probs)

    # ------------------------------------------------------------------
    # State accessors (performance data from attempt history)
    # ------------------------------------------------------------------

    def _objective_weights(self) -> Dict[str, float]:
        return self.config.objective_profiles[self.primary_objective]

    def _overall_stats(self) -> Dict[str, float]:
        return self._safe_stats(self.performance_state.get("overall"))

    def _kc_stats(self, kc: str) -> Dict[str, float]:
        return self._safe_stats((self.performance_state.get("kc_stats") or {}).get(kc))

    def _tag_stats(self, kc: str, tag: str) -> Dict[str, float]:
        tag_stats = self.performance_state.get("tag_stats") or {}
        nested = tag_stats.get(kc, {})
        if isinstance(nested, dict) and isinstance(nested.get(tag), dict):
            return self._safe_stats(nested.get(tag))
        if isinstance(tag_stats.get(tag), dict):
            return self._safe_stats(tag_stats.get(tag))
        return self._safe_stats(None)

    def _difficulty_stats(self, difficulty: int) -> Dict[str, float]:
        difficulty_stats = self.performance_state.get("difficulty_stats") or {}
        if str(difficulty) in difficulty_stats:
            return self._safe_stats(difficulty_stats[str(difficulty)])
        if difficulty in difficulty_stats:
            return self._safe_stats(difficulty_stats[difficulty])
        return self._safe_stats(None)

    def _recent_state(self) -> Dict[str, List[Any]]:
        recent = self.performance_state.get("recent") or {}
        return {
            "kcs":         list(recent.get("kcs", []) or []),
            "tags":        list(recent.get("tags", []) or []),
            "difficulties":list(recent.get("difficulties", []) or []),
            "courses":     [self._normalize_course_label(x) for x in list(recent.get("courses", []) or [])],
        }

    # ------------------------------------------------------------------
    # Course selection
    # ------------------------------------------------------------------

    def _course_weight_map(self, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> Dict[str, float]:
        idx = self.config.course_order.index(self.course_level)
        if not self.allow_cross_course:
            return {self.course_level: 1.0}
        overall_acc = self._smoothed_accuracy(self._overall_stats())
        low  = self._trap(overall_acc, 0.0, 0.0, 0.45, 0.62)
        mid  = self._tri(overall_acc,  0.45, 0.65, 0.85)
        high = self._trap(overall_acc, 0.70, 0.85, 1.0, 1.0)
        weights: Dict[str, float] = {self.course_level: 1.0}
        if idx > 0:
            prev_course = self.config.course_order[idx - 1]
            weights[prev_course] = 0.05 + 0.55 * low + 0.10 * mid
        if idx + 1 < len(self.config.course_order):
            next_course = self.config.course_order[idx + 1]
            weights[next_course] = self.config.alpha_cross_course + 0.55 * high + 0.10 * mid
            if self.primary_objective == "LEARN_NEW_CONTENT":
                weights[next_course] += 0.15
        if session_state is not None:
            course_counts = session_state.get("course_counts", {})
            recent_courses = self._recent_state()["courses"]
            for course in list(weights.keys()):
                recent_penalty  = 0.10 * self._recent_count(recent_courses, course)
                session_penalty = 0.10 * int(course_counts.get(course, 0))
                weights[course] = max(weights[course] - recent_penalty - session_penalty, 1e-3)
        return weights

    def _sample_course(self, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> str:
        return str(self._weighted_choice(self._course_weight_map(session_state)))

    # ------------------------------------------------------------------
    # KC scoring  ← BKT integration lives here
    # ------------------------------------------------------------------

    def _kc_score(self, kc: str, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> float:
        objective = self._objective_weights()
        recent    = self._recent_state()
        stats     = self._kc_stats(kc)

        interest    = self._normalize_preference(self.kc_scores.get(kc), self.config.default_kc_score)
        need        = self._need_for_kc(kc, stats)   # ← BKT-aware
        uncertainty = self._uncertainty(stats)         # ← always from attempt count

        diversity_bonus = 1.0
        session_count   = 0
        if session_state is not None:
            session_count   = int(session_state.get("kc_counts", {}).get(kc, 0))
            diversity_bonus = 1.0 / (1.0 + session_count)

        score = (
            objective["interest"]     * interest
            + objective["need"]       * need
            + objective["uncertainty"]* uncertainty
            + objective["diversity"]  * diversity_bonus
        )

        recent_penalty  = 0.12 * self._recent_count(recent["kcs"], kc)
        session_penalty = self._session_penalty(session_count, self.config.repetition_limit_per_kc)
        score = score - recent_penalty - session_penalty

        # Objective-specific bonuses
        if self.primary_objective == "LEARN_NEW_CONTENT" and stats["attempts"] == 0:
            score += 0.18
        if self.primary_objective == "IMPROVE_GRADES" and stats["attempts"] >= 3 and need >= 0.40:
            score += 0.12

        return max(score, 1e-3)

    def _sample_kc(self, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> str:
        return str(self._weighted_choice({kc: self._kc_score(kc, session_state) for kc in self.taxonomy.keys()}))

    # ------------------------------------------------------------------
    # Tag scoring
    # ------------------------------------------------------------------

    def _tag_preference_score(self, kc: str, tag: str) -> Optional[float]:
        per_kc = self.tag_scores.get(kc)
        if isinstance(per_kc, dict):
            return per_kc.get(tag)
        flat_value = self.tag_scores.get(tag)
        if isinstance(flat_value, (int, float)):
            return float(flat_value)
        return None

    def _tag_score(self, kc: str, tag: str, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> float:
        recent  = self._recent_state()
        interest    = self._normalize_preference(self._tag_preference_score(kc, tag), self.config.default_tag_score)
        stats       = self._tag_stats(kc, tag)
        need        = self._need(stats)       # tags don't have BKT state, use heuristic
        uncertainty = self._uncertainty(stats)
        session_count   = 0
        diversity_bonus = 1.0
        if session_state is not None:
            session_count   = int(session_state.get("tag_counts", {}).get(tag, 0))
            diversity_bonus = 1.0 / (1.0 + session_count)
        score = 0.50 * interest + 0.25 * need + 0.10 * uncertainty + 0.15 * diversity_bonus
        recent_penalty  = 0.10 * self._recent_count(recent["tags"], tag)
        session_penalty = self._session_penalty(session_count, self.config.repetition_limit_per_tag)
        return max(score - recent_penalty - session_penalty, 1e-3)

    def _sample_tag(self, kc: str, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> str:
        tags = self.taxonomy.get(kc, [])
        if not tags:
            raise ValueError(f"KC '{kc}' has no tags in taxonomy")
        return str(self._weighted_choice({tag: self._tag_score(kc, tag, session_state) for tag in tags}))

    # ------------------------------------------------------------------
    # Difficulty: fuzzy logic controller
    # ------------------------------------------------------------------

    def _difficulty_shift_from_fuzzy_rules(self, kc: str) -> float:
        overall  = self._overall_stats()
        kc_stats = self._kc_stats(kc)
        overall_acc = self._smoothed_accuracy(overall)
        kc_acc      = self._smoothed_accuracy(kc_stats) if kc_stats["attempts"] > 0 else overall_acc
        blended_acc = 0.60 * kc_acc + 0.40 * overall_acc
        seconds     = kc_stats["avg_seconds"] if kc_stats["attempts"] > 0 else overall["avg_seconds"]
        speed_score = self._clip01((120.0 - seconds) / 90.0)

        acc_low  = self._trap(blended_acc, 0.0,  0.0,  0.45, 0.62)
        acc_mid  = self._tri( blended_acc, 0.45, 0.65, 0.85)
        acc_high = self._trap(blended_acc, 0.70, 0.85, 1.0,  1.0)

        speed_slow = self._trap(1.0 - speed_score, 0.0,  0.0,  0.45, 0.70)
        speed_ok   = self._tri( speed_score,        0.25, 0.55, 0.80)
        speed_fast = self._trap(speed_score,        0.60, 0.80, 1.0,  1.0)

        down_strong = acc_low
        keep        = max(acc_mid, min(acc_high, speed_slow))
        up_strong   = min(acc_high, speed_fast)
        up_mild     = min(acc_high, speed_ok)
        down_extra  = min(acc_low,  speed_slow)

        numerator   = (-1.00 * down_strong - 1.25 * down_extra
                       + 0.00 * keep
                       + 0.60 * up_mild    + 1.00 * up_strong)
        denominator = down_strong + down_extra + keep + up_mild + up_strong
        shift = 0.0 if denominator <= 1e-8 else numerator / denominator

        if self.primary_objective == "LEARN_NEW_CONTENT" and acc_high > 0.4:
            shift += 0.25
        elif self.primary_objective == "IMPROVE_GRADES" and acc_low > 0.4:
            shift -= 0.20

        return float(np.clip(shift, -1.5, 1.5))

    def _difficulty_weight_map(self, kc: str, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> Dict[int, float]:
        target = float(self.profile_target_difficulty) + self._difficulty_shift_from_fuzzy_rules(kc)
        target = float(np.clip(target, self.min_difficulty, self.max_difficulty))
        weights: Dict[int, float] = {}
        recent = self._recent_state()
        for d in range(self.min_difficulty, self.max_difficulty + 1):
            base         = float(np.exp(-((d - target) ** 2) / (2.0 * (self.config.difficulty_sigma ** 2))))
            diff_stats   = self._difficulty_stats(d)
            diff_acc     = self._smoothed_accuracy(diff_stats)
            calibration  = 1.0 - 0.35 * abs(diff_acc - 0.72)
            recent_penalty  = 0.08 * self._recent_count(recent["difficulties"], d)
            session_penalty = 0.0
            if session_state is not None:
                session_count   = int(session_state.get("difficulty_counts", {}).get(d, 0))
                session_penalty = 0.08 * session_count
            weights[d] = max(base * calibration - recent_penalty - session_penalty, 1e-3)
        return weights

    def _sample_difficulty(self, kc: str, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> int:
        return int(self._weighted_choice(self._difficulty_weight_map(kc, session_state)))

    # ------------------------------------------------------------------
    # Session generation
    # ------------------------------------------------------------------

    def recommendation(self, session_state: Optional[Dict[str, Dict[Any, int]]] = None) -> Tuple[str, str, str, int]:
        course     = self._sample_course(session_state)
        kc         = self._sample_kc(session_state)
        tag        = self._sample_tag(kc, session_state)
        difficulty = self._sample_difficulty(kc, session_state)
        return course, kc, tag, difficulty

    def generate_session(self, n_problems: int) -> List[Tuple[str, str, str, int]]:
        session: List[Tuple[str, str, str, int]] = []
        session_state: Dict[str, Dict[Any, int]] = {
            "course_counts":     {},
            "kc_counts":         {},
            "tag_counts":        {},
            "difficulty_counts": {},
        }
        for _ in range(n_problems):
            course, kc, tag, difficulty = self.recommendation(session_state=session_state)
            session.append((course, kc, tag, difficulty))
            session_state["course_counts"][course]         = session_state["course_counts"].get(course, 0) + 1
            session_state["kc_counts"][kc]                 = session_state["kc_counts"].get(kc, 0) + 1
            session_state["tag_counts"][tag]               = session_state["tag_counts"].get(tag, 0) + 1
            session_state["difficulty_counts"][difficulty] = session_state["difficulty_counts"].get(difficulty, 0) + 1
        return session