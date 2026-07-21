"""Normalization helpers for messy real-world data from monday.com boards."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from dateutil import parser as dateparser
from rapidfuzz import fuzz, process


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

def normalize_dates(series: pd.Series) -> pd.Series:
    """Parse mixed date formats into consistent ISO timestamps.

    Handles DD/MM/YYYY, MM-DD-YY, Month D YYYY, Excel serial dates,
    ISO strings, and more.  Unparseable values become NaT.
    """
    def _parse(val: Any) -> Any:
        if pd.isna(val) or str(val).strip() == "":
            return pd.NaT
        s = str(val).strip()
        # Excel serial date (numeric > 40000)
        try:
            num = float(s)
            if 40000 < num < 60000:
                return datetime(1899, 12, 30) + timedelta(days=num)
        except (ValueError, OverflowError):
            pass
        try:
            return dateparser.parse(s, dayfirst=True, fuzzy=True)
        except (ValueError, OverflowError, TypeError):
            return pd.NaT

    return series.apply(_parse)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_text(series: pd.Series, title_case: bool = True) -> pd.Series:
    """Strip whitespace, collapse duplicate spaces, optionally title-case."""
    def _clean(val: Any) -> str:
        if pd.isna(val):
            return ""
        s = str(val).strip()
        s = re.sub(r"\s+", " ", s)
        if title_case:
            s = s.title()
        return s
    return series.apply(_clean)


# ---------------------------------------------------------------------------
# Categorical / fuzzy normalization
# ---------------------------------------------------------------------------

def normalize_categorical(
    series: pd.Series,
    mapping: dict[str, str] | None = None,
    threshold: int = 85,
) -> pd.Series:
    """Fuzzy-cluster near-duplicate category labels.

    First applies any explicit mapping, then clusters remaining values
    using rapidfuzz ratio at the given threshold (case-insensitively).
    """
    result = series.copy()

    # Apply explicit mapping first
    if mapping:
        result = result.replace(mapping)

    # Gather unique non-null values
    unique_vals = [v for v in result.unique() if v and str(v).strip() and not pd.isna(v)]
    if not unique_vals:
        return result

    # Build clusters: first value encountered becomes canonical
    canonical_map: dict[str, str] = {}
    canonical_list: list[str] = []
    canonical_lower_list: list[str] = []

    for val in unique_vals:
        if val in canonical_map:
            continue
        val_lower = str(val).strip().lower()
        match = process.extractOne(val_lower, canonical_lower_list, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            idx = match[2]
            canonical_map[val] = canonical_list[idx]
        else:
            canonical_map[val] = val
            canonical_list.append(val)
            canonical_lower_list.append(val_lower)

    return result.map(lambda x: canonical_map.get(x, x) if pd.notna(x) and str(x).strip() else x)



# ---------------------------------------------------------------------------
# Currency normalization
# ---------------------------------------------------------------------------

def normalize_currency(series: pd.Series) -> pd.Series:
    """Strip currency symbols, commas, handle K/L/Cr suffixes, cast to float."""
    def _parse(val: Any) -> float | None:
        if pd.isna(val) or str(val).strip() == "":
            return None
        s = str(val).strip()
        # Remove currency symbols and commas
        s = re.sub(r"[₹$€£,]", "", s).strip()
        if not s:
            return None
        multiplier = 1.0
        upper_s = s.upper()
        if re.search(r"\d\s*CR$", upper_s):
            multiplier = 10_000_000
            s = re.sub(r"\s*CR$", "", s, flags=re.IGNORECASE).strip()
        elif re.search(r"\d\s*L$", upper_s):
            multiplier = 100_000
            s = re.sub(r"\s*L$", "", s, flags=re.IGNORECASE).strip()
        elif re.search(r"\d\s*K$", upper_s):
            multiplier = 1_000
            s = re.sub(r"\s*K$", "", s, flags=re.IGNORECASE).strip()
        try:
            return float(s) * multiplier
        except (ValueError, OverflowError):
            return None

    return series.apply(_parse)



# ---------------------------------------------------------------------------
# Sector normalization
# ---------------------------------------------------------------------------

SECTOR_MAPPING = {
    "energy": "Renewables",
    "power/energy": "Renewables",
    "solar": "Renewables",
    "wind": "Renewables",
    "powerline": "Powerline",
    "power line": "Powerline",
    "power grid": "Powerline",
    "railroad": "Railways",
    "rail": "Railways",
    "construction": "Construction",
    "security": "Security and Surveillance",
    "surveillance": "Security and Surveillance",
    "security and surveillance": "Security and Surveillance",
    "mining": "Mining",
    "dsp": "DSP",
    "tender": "Tender",
    "manufacturing": "Manufacturing",
    "aviation": "Aviation",
    "others": "Others",
    "other": "Others",
}


def normalize_sector(series: pd.Series) -> pd.Series:
    """Normalize sector/industry names using fuzzy matching."""
    mapped = normalize_text(series, title_case=False)
    mapped = normalize_categorical(mapped, mapping=SECTOR_MAPPING, threshold=80)
    return mapped


# ---------------------------------------------------------------------------
# Missing data reporting
# ---------------------------------------------------------------------------

def flag_missing(df: pd.DataFrame) -> dict[str, Any]:
    """Return per-column % missing and a list of data-quality notes."""
    report: dict[str, Any] = {}
    notes: list[str] = []
    total = len(df)
    if total == 0:
        return {"columns": {}, "notes": ["DataFrame is empty."], "row_count": 0}

    for col in df.columns:
        missing_count = int(df[col].isna().sum()) + int((df[col].astype(str).str.strip() == "").sum())
        pct = round(missing_count / total * 100, 1)
        report[col] = {"missing_count": missing_count, "missing_pct": pct}
        if pct > 0:
            notes.append(f"{col}: {pct}% missing ({missing_count}/{total} rows)")

    return {"columns": report, "notes": notes, "row_count": total}


# ---------------------------------------------------------------------------
# Deal-stage normalization (specific to the Skylark data)
# ---------------------------------------------------------------------------

DEAD_STATUS_MAPPING = {
    "Dead": "Lost",
    "dead": "Lost",
    "DEAD": "Lost",
}

WIN_RATE_STAGES_WON = {"Won", "G. Project Won", "H. Work Order Received", "Project Completed", "K. Amount Accrued", "J. Invoice sent"}


def normalize_deal_status(series: pd.Series) -> pd.Series:
    """Map 'Dead' to 'Lost', clean up whitespace."""
    return normalize_categorical(series, mapping=DEAD_STATUS_MAPPING, threshold=95)


def is_won_stage(stage: str) -> bool:
    """Check if a deal stage represents a won deal."""
    if not stage or pd.isna(stage):
        return False
    s = str(stage).strip()
    return s in WIN_RATE_STAGES_WON


def is_active_stage(stage: str) -> bool:
    """Check if a deal stage is in the active pipeline (not won, not lost, not dead)."""
    if not stage or pd.isna(stage):
        return False
    s = str(stage).strip()
    dead_stages = {"L. Project Lost", "N. Not relevant at the moment", "O. Not Relevant at all", "M. Projects On Hold"}
    return s not in dead_stages and not is_won_stage(s)
