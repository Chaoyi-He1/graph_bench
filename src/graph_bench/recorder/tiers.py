from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_bench.recorder.models import Tier
    from graph_bench.user_simulator.models import SolutionCall


def classify_tier(call: SolutionCall, *, forced_reveal: bool) -> Tier:
    """
    Deterministic §9.2 tier from a solution call.

    Precedence: forced_reveal > shortcut (defer to judge) > L1/L2 missing
    (blind) > only-L3 missing (degrade) > all satisfied (informed).
    """
    if forced_reveal:
        return 'forced_reveal'
    if call.is_shortcut:
        return 'needs_inference_check'
    missing = call.missing_required_info
    if missing.L1 or missing.L2:
        return 'blind_guess'
    if missing.L3:
        return 'degrade_to_shortcut'
    return 'informed'
