"""
Agentic self-checking layer for the recommender.

Wraps recommend_songs() in a plan -> act -> check loop instead of calling it once
and trusting the output:

  1. Plan  - pick a set of scoring weights (starts at the defaults).
  2. Act   - run recommend_songs() with those weights to get a ranked top-k list.
  3. Check - inspect the #1 pick against guardrail rules (is its score high enough
             to call "confident"? is its energy actually close to what the user
             asked for, even if genre/mood matched?).
  4. If a check fails and attempts remain, re-plan by adjusting weights and retry.
     Otherwise stop and report whether the final result is confident.

This targets a known failure mode of the plain scoring rule (documented in
model_card.md): a strong genre+mood match can outrank every other song even when
its energy is nowhere near the user's target, and the plain score gives no signal
that this happened. The agent can't rewrite the catalog's data, so a bad match
sometimes can't be fixed by re-weighting alone -- but it will always surface that
mismatch explicitly instead of reporting a bad recommendation as a good one.
"""

import logging
from typing import Dict, List, Optional

from .recommender import DEFAULT_WEIGHTS, recommend_songs

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
ENERGY_GAP_THRESHOLD = 0.35
MIN_CONFIDENT_SCORE = 1.0
ENERGY_WEIGHT_STEP = 1.0


def _check(user_prefs: Dict, top_song: Dict, top_score: float) -> List[str]:
    """Returns a list of guardrail violations for the top-ranked recommendation."""
    issues = []

    target_energy = user_prefs.get("energy")
    if target_energy is not None:
        gap = abs(top_song["energy"] - target_energy)
        if gap > ENERGY_GAP_THRESHOLD:
            issues.append(
                f"energy_mismatch: top pick's energy ({top_song['energy']:.2f}) is "
                f"{gap:.2f} away from the requested target ({target_energy:.2f})"
            )

    if top_score < MIN_CONFIDENT_SCORE:
        issues.append(
            f"low_confidence: top score ({top_score:.2f}) is below the "
            f"confidence floor ({MIN_CONFIDENT_SCORE:.2f})"
        )

    return issues


def recommend_with_agent(user_prefs: Dict, songs: List[Dict], k: int = 5) -> Dict:
    """Runs the plan -> act -> check loop and returns recommendations plus a trace.

    Return shape:
      {
        "recommendations": [(song, score, explanation), ...],
        "trace": [{"attempt": int, "weights": {...}, "issues": [...]}, ...],
        "confident": bool,
      }
    """
    weights = dict(DEFAULT_WEIGHTS)
    trace = []
    ranked = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info("Attempt %d: scoring catalog with weights=%s", attempt, weights)
        ranked = recommend_songs(user_prefs, songs, k=k, weights=weights)
        top_song, top_score, _ = ranked[0]

        issues = _check(user_prefs, top_song, top_score)
        trace.append({"attempt": attempt, "weights": dict(weights), "issues": issues})

        if not issues:
            logger.info("Attempt %d passed all guardrails.", attempt)
            break

        logger.warning("Attempt %d flagged issues: %s", attempt, issues)

        # Raising the energy weight only ever helps an energy_mismatch issue -- it
        # can't manufacture a genre/mood match that isn't in the catalog. Retrying
        # for any other issue would just burn attempts on a fix that can't work, so
        # only continue when there's a real lever left to pull.
        can_retry = attempt < MAX_ATTEMPTS and any(
            issue.startswith("energy_mismatch") for issue in issues
        )

        if can_retry:
            weights["energy"] += ENERGY_WEIGHT_STEP
            logger.info(
                "Re-planning: raising energy weight to %.2f and retrying.",
                weights["energy"],
            )
        else:
            logger.warning(
                "Stopping after attempt %d; returning best-effort recommendations "
                "with the mismatch flagged instead of hiding it.",
                attempt,
            )
            break

    return {
        "recommendations": ranked,
        "trace": trace,
        "confident": not trace[-1]["issues"],
    }
