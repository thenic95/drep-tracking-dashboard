import logging
from datetime import date

from sqlalchemy.orm import Session

from . import database

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "mature_cohort_days": "180",
    "exception_tenure_days": "60",
    "exception_participation_pct": "40.0",
    "part_lower_bound_pct": "50.0",
    "part_upper_bound_pct": "67.0",
    "impact_minimum_pct": "30.0",
    # Legacy keys kept for backward-compat reads; unused by new logic
    "tenure_days": "180",
    "cf_impact_ratio": "15.0",
    "participation_rate": "70.0",
    "rationale_rate": "50.0",
    "alignment_score": "3",
    "min_risk_factors": "2",
}


INT_KEYS = {"mature_cohort_days", "exception_tenure_days", "tenure_days", "alignment_score", "min_risk_factors"}


def get_thresholds(db: Session) -> dict:
    """Reads thresholds from DB, falling back to defaults."""
    stored = database.get_cf_thresholds(db)
    result = {}
    for key, default_val in DEFAULT_THRESHOLDS.items():
        val = stored.get(key, default_val)
        if key in INT_KEYS:
            result[key] = int(val)
        else:
            result[key] = float(val)
    return result


def compute_drep_metrics(
    db: Session, drep_data: dict, current_epoch: int, thresholds: dict
) -> dict:
    """
    Computes CF delegation metrics for a single DRep.
    Returns a dict with computed fields to merge into the response.
    """
    drep_id = drep_data["drep_id"]
    delegation_epoch = drep_data.get("delegation_epoch")
    cf_delegated_ada = drep_data.get("cf_delegated_ada") or 0
    total_voting_power = drep_data.get("total_voting_power") or 0
    alignment_score = drep_data.get("alignment_score")

    # Tenure — computed from user-set delegation_date to today
    delegation_date_str = drep_data.get("delegation_date")
    tenure_days = None
    if delegation_date_str:
        try:
            tenure_days = (date.today() - date.fromisoformat(delegation_date_str)).days
        except ValueError:
            pass

    # CF Impact Ratio
    cf_impact_ratio = 0.0
    if total_voting_power > 0 and cf_delegated_ada > 0:
        # Convert cf_delegated_ada to lovelace for comparison
        cf_lovelace = cf_delegated_ada * 1_000_000
        cf_impact_ratio = (cf_lovelace / total_voting_power) * 100

    # Participation rate — based on registration_epoch (when the DRep became active)
    registration_epoch = drep_data.get("registration_epoch")
    participation_rate = 0.0
    votes_cast = None
    total_gas = None
    if registration_epoch is not None:
        total_gas = database.count_gas_since_epoch(db, registration_epoch)
        votes_cast = database.count_drep_votes_since_epoch(db, drep_id, registration_epoch)
        if total_gas > 0:
            participation_rate = (votes_cast / total_gas) * 100

    # Rationale rate — also based on registration_epoch
    rationale_rate = 0.0
    if registration_epoch is not None:
        votes_with_rationale = database.count_drep_votes_with_rationale(
            db, drep_id, registration_epoch
        )
        if votes_cast > 0:
            rationale_rate = (votes_with_rationale / votes_cast) * 100

    # Cache non-zero computed metrics for persistence across restarts
    cache_updates = {}
    if participation_rate > 0:
        cache_updates["cached_participation_rate"] = round(participation_rate, 1)
    if rationale_rate > 0:
        cache_updates["cached_rationale_rate"] = round(rationale_rate, 1)
    if cf_impact_ratio > 0:
        cache_updates["cached_cf_impact_ratio"] = round(cf_impact_ratio, 1)
    if cache_updates:
        database.update_drep_cached_metrics(db, drep_id, cache_updates)

    # Fallback to cached values when live computation returns 0
    if participation_rate == 0 and drep_data.get("cached_participation_rate"):
        participation_rate = drep_data["cached_participation_rate"]
    if rationale_rate == 0 and drep_data.get("cached_rationale_rate"):
        rationale_rate = drep_data["cached_rationale_rate"]
    if cf_impact_ratio == 0 and drep_data.get("cached_cf_impact_ratio"):
        cf_impact_ratio = drep_data["cached_cf_impact_ratio"]

    # --- 5-Gate Reallocation Decision Tree ---
    is_at_risk = False
    failed_gate = None

    mature_days = thresholds.get("mature_cohort_days", 180)
    exception_tenure = thresholds.get("exception_tenure_days", 60)
    exception_part = thresholds.get("exception_participation_pct", 40.0)
    part_lower = thresholds.get("part_lower_bound_pct", 50.0)
    part_upper = thresholds.get("part_upper_bound_pct", 67.0)
    impact_min = thresholds.get("impact_minimum_pct", 30.0)

    is_mature = tenure_days is not None and tenure_days >= mature_days

    # Gate 1 — Maturity Check
    if not is_mature:
        # Exception rule: newer DRep with tenure >= exception_tenure AND participation < exception threshold
        exception_applies = (
            tenure_days is not None
            and tenure_days >= exception_tenure
            and participation_rate < exception_part
        )
        if not exception_applies:
            # SAFE — new DRep without exception → skip remaining gates
            pass  # is_at_risk stays False
        else:
            # Exception triggered → continue to Gate 2
            is_at_risk, failed_gate = _evaluate_gates_2_through_5(
                participation_rate, alignment_score, cf_impact_ratio,
                part_lower, part_upper, impact_min,
            )
    else:
        # Mature DRep → continue to Gate 2
        is_at_risk, failed_gate = _evaluate_gates_2_through_5(
            participation_rate, alignment_score, cf_impact_ratio,
            part_lower, part_upper, impact_min,
        )

    return {
        "tenure_days": tenure_days,
        "cf_impact_ratio": round(cf_impact_ratio, 1),
        "participation_rate": round(participation_rate, 1),
        "rationale_rate": round(rationale_rate, 1),
        "is_at_risk": is_at_risk,
        "failed_gate": failed_gate,
        "votes_cast": votes_cast if registration_epoch is not None else None,
        "total_gas": total_gas if registration_epoch is not None else None,
    }


def _evaluate_gates_2_through_5(
    participation_rate: float,
    alignment_score: int | None,
    cf_impact_ratio: float,
    part_lower: float,
    part_upper: float,
    impact_min: float,
) -> tuple[bool, str | None]:
    """Run Gates 2–5 and return (is_at_risk, failed_gate)."""

    # Gate 2 — Participation
    if participation_rate < part_lower:
        return True, f"Gate 2: Part. < {part_lower:.0f}%"
    if participation_rate > part_upper:
        return False, None  # SAFE

    # Gate 3 — Rationale (manual ranking step; pass through to Gate 4)
    # DReps in the 50%-67% bracket proceed

    # Gate 4 — Alignment
    if alignment_score is not None and alignment_score < 3:
        return True, f"Gate 4: Alignment < 3"
    if alignment_score is None:
        # No score set — cannot clear Gate 4; flag for manual review
        return True, "Gate 4: Alignment not set"

    # Gate 5 — Power Indicator
    if cf_impact_ratio < impact_min:
        return True, f"Gate 5: Impact < {impact_min:.0f}%"

    return False, None  # SAFE
