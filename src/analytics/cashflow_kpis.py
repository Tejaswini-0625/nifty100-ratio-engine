"""Cash flow KPIs: FCF, CFO Quality, CapEx Intensity, FCF Conversion, Capital Allocation classifier."""

from typing import Optional, List


def free_cash_flow(operating_activity: float, investing_activity: float) -> float:
    """FCF = CFO + CFI. Negative value is allowed."""
    return operating_activity + investing_activity


def cfo_quality_score(cfo_values: List[float], pat_values: List[float]) -> Optional[str]:
    """CFO / PAT ratio averaged over up to 5 years.
    >1.0 = High Quality, 0.5-1.0 = Moderate, <0.5 = Accrual Risk. None if any PAT = 0 (skipped from avg);
    None overall if no valid years.
    """
    ratios = []
    for cfo, pat in zip(cfo_values, pat_values):
        if pat == 0:
            continue
        ratios.append(cfo / pat)
    if not ratios:
        return None
    avg_ratio = sum(ratios) / len(ratios)
    if avg_ratio > 1.0:
        return "High Quality"
    elif avg_ratio >= 0.5:
        return "Moderate"
    else:
        return "Accrual Risk"


def cfo_quality_score_numeric(cfo_values: List[float], pat_values: List[float]) -> Optional[float]:
    """Same as cfo_quality_score but returns the raw averaged numeric ratio (None if PAT always 0)."""
    ratios = [cfo / pat for cfo, pat in zip(cfo_values, pat_values) if pat != 0]
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


def capex_intensity(investing_activity: float, sales: float) -> Optional[float]:
    """CapEx Intensity % = abs(investing_activity) / sales * 100. None if sales = 0."""
    if sales == 0:
        return None
    return (abs(investing_activity) / sales) * 100


def capex_intensity_label(intensity_pct: Optional[float]) -> Optional[str]:
    """<3% = Asset Light, 3-8% = Moderate, >8% = Capital Intensive."""
    if intensity_pct is None:
        return None
    if intensity_pct < 3:
        return "Asset Light"
    elif intensity_pct <= 8:
        return "Moderate"
    else:
        return "Capital Intensive"


def fcf_conversion_rate(fcf: float, operating_profit: float) -> Optional[float]:
    """FCF Conversion % = FCF / operating_profit * 100. None if operating_profit = 0."""
    if operating_profit == 0:
        return None
    return (fcf / operating_profit) * 100


# ---------------------------------------------------------------------------
# Capital Allocation 8-Pattern Classifier
# ---------------------------------------------------------------------------

_PATTERN_LABELS = {
    ("+", "-", "-"): "Reinvestor",              # or Shareholder Returns if CFO/PAT high (sub-classified below)
    ("+", "+", "-"): "Liquidating Assets",
    ("-", "+", "+"): "Distress Signal",
    ("-", "-", "+"): "Growth Funded by Debt",
    ("+", "+", "+"): "Cash Accumulator",
    ("-", "-", "-"): "Pre-Revenue",
    ("+", "-", "+"): "Mixed",
    ("-", "+", "-"): "Mixed",  # not explicitly listed in spec; default bucket
}


def _sign(value: float) -> str:
    return "+" if value >= 0 else "-"


def capital_allocation_pattern(cfo: float, cfi: float, cff: float,
                                 cfo_pat_ratio: Optional[float] = None,
                                 high_quality_threshold: float = 1.0) -> dict:
    """Classify capital allocation pattern based on sign of (CFO, CFI, CFF).

    Returns dict with cfo_sign, cfi_sign, cff_sign, pattern_label.
    Sub-classifies (+,-,-) as 'Shareholder Returns' if CFO/PAT ratio is high (>= threshold),
    otherwise 'Reinvestor'.
    """
    cfo_sign, cfi_sign, cff_sign = _sign(cfo), _sign(cfi), _sign(cff)
    key = (cfo_sign, cfi_sign, cff_sign)
    label = _PATTERN_LABELS.get(key, "Mixed")

    if key == ("+", "-", "-") and cfo_pat_ratio is not None and cfo_pat_ratio >= high_quality_threshold:
        label = "Shareholder Returns"

    return {
        "cfo_sign": cfo_sign,
        "cfi_sign": cfi_sign,
        "cff_sign": cff_sign,
        "pattern_label": label,
    }
