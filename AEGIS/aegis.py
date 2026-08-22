#!/usr/bin/env python3

"""
AEGIS — Autonomous Evidence-Grounded Inspection System

Lifecycle:

INPUT
  -> OBSERVATION
  -> STRUCTURE
  -> DATA QUALITY
  -> VALIDITY
  -> PATTERNS
  -> RELATIONSHIPS
  -> ANOMALIES
  -> DUPLICATES
  -> MISSINGNESS
  -> PLACEHOLDERS
  -> EVIDENCE
  -> FINDINGS
  -> PRIORITY
  -> ACTION QUEUE
  -> ACTION LEDGER
  -> RE-OBSERVATION
  -> VERIFICATION
  -> AUDIT
  -> FINAL STATE

Design principles:
- Never invent source data.
- Never silently mutate the supplied source.
- Findings are evidence-backed.
- Recommendations are separate from observations.
- Actions are recorded separately from findings.
- Verification requires a fresh observation.
- Every run is reproducible.
- JSON report is the authoritative machine-readable artifact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VERSION = "7.0"
STATUS_OPEN = "OPEN"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_RESOLVED = "RESOLVED"
STATUS_VERIFIED = "VERIFIED"
STATUS_DISMISSED = "DISMISSED"
STATUS_REOPENED = "REOPENED"


# ============================================================
# UTILITIES
# ============================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def is_missing(value: Any) -> bool:
    if value is None:
        return True

    s = str(value).strip().lower()

    return s in {
        "",
        "null",
        "none",
        "nan",
        "n/a",
        "na",
        "unknown",
        "missing",
    }


def normalize_value(value: Any) -> str:
    return "" if value is None else str(value).strip()


def row_completeness(row: Dict[str, str], fields: List[str]) -> float:
    if not fields:
        return 0.0

    populated = sum(
        1 for field in fields
        if not is_missing(row.get(field))
    )

    return populated / len(fields)


def make_id(prefix: str, payload: Any) -> str:
    digest = sha256_text(stable_json(payload))[:12]
    return f"{prefix}-{digest}"


# ============================================================
# DATA INGESTION
# ============================================================

class Dataset:
    def __init__(
        self,
        source: Path,
        fields: List[str],
        rows: List[Dict[str, str]],
    ):
        self.source = source
        self.fields = fields
        self.rows = rows

    @classmethod
    def load_csv(cls, path: Path) -> "Dataset":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                raise ValueError("CSV contains no header.")

            fields = [
                str(x).strip()
                for x in reader.fieldnames
                if x is not None
            ]

            rows = []

            for raw in reader:
                row = {}

                for field in fields:
                    value = raw.get(field, "")
                    row[field] = "" if value is None else str(value).strip()

                rows.append(row)

        return cls(path, fields, rows)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "source": str(self.source),
            "sha256": sha256_file(self.source),
            "bytes": self.source.stat().st_size,
            "fields": self.fields,
            "rows": len(self.rows),
        }


# ============================================================
# FIELD CLASSIFICATION
# ============================================================

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

PHONE_RE = re.compile(
    r"^\+?[0-9][0-9 .()\-]{6,}[0-9]$"
)

URL_RE = re.compile(
    r"^(https?://|www\.)",
    re.IGNORECASE
)

INSTAGRAM_RE = re.compile(
    r"^@?[A-Za-z0-9._]{1,30}$"
)

PLACEHOLDER_TOKENS = {
    "test",
    "testing",
    "placeholder",
    "default",
    "dummy",
    "example",
    "sample",
    "unknown",
    "changeme",
    "tbd",
    "todo",
    "n/a",
    "na",
    "none",
    "null",
    "user@domain.com",
    "example@example.com",
    "john@example.com",
    "dead-500",
}


def field_kind(field: str) -> str:
    f = field.lower().strip()

    if "email" in f or f in {"mail", "e-mail"}:
        return "email"

    if (
        "phone" in f
        or "mobile" in f
        or "telephone" in f
        or f in {"tel", "cell"}
    ):
        return "phone"

    if (
        f in {"ig", "instagram"}
        or "instagram" in f
    ):
        return "ig"

    if (
        "url" in f
        or "website" in f
        or "link" in f
    ):
        return "url"

    if (
        "id" in f
        or "name" in f
        or "status" in f
        or "type" in f
        or "category" in f
    ):
        return "text"

    return "text"


def validate_value(kind: str, value: str) -> Tuple[bool, str]:
    if is_missing(value):
        return False, "missing"

    s = value.strip()

    if kind == "email":
        return bool(EMAIL_RE.match(s)), "email_format"

    if kind == "phone":
        digits = re.sub(r"\D", "", s)
        return len(digits) >= 7, "phone_format"

    if kind == "ig":
        if URL_RE.match(s):
            return True, "url_style"

        return bool(INSTAGRAM_RE.match(s)), "ig_format"

    if kind == "url":
        return bool(URL_RE.match(s)), "url_format"

    return True, "text"


def looks_like_placeholder(value: str) -> bool:
    if is_missing(value):
        return False

    s = value.strip().lower()

    if s in PLACEHOLDER_TOKENS:
        return True

    if "example.com" in s:
        return True

    if s.startswith("test-") or s.endswith("-test"):
        return True

    return False


# ============================================================
# ENGINE
# ============================================================

class AEGIS:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset
        self.findings: List[Dict[str, Any]] = []
        self.audit: List[Dict[str, Any]] = []
        self.actions: List[Dict[str, Any]] = []

        self.report: Dict[str, Any] = {}

        self.add_audit(
            "SYSTEM_START",
            "AEGIS analysis initialized",
            {
                "version": VERSION,
                "timestamp": now_iso(),
            },
        )

    # --------------------------------------------------------
    # AUDIT
    # --------------------------------------------------------

    def add_audit(
        self,
        event: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.audit.append({
            "timestamp": now_iso(),
            "event": event,
            "description": description,
            "details": details or {},
        })

    # --------------------------------------------------------
    # FINDINGS
    # --------------------------------------------------------

    def add_finding(
        self,
        category: str,
        severity: str,
        title: str,
        basis: str,
        evidence_score: float,
        affected_rows: Optional[List[int]] = None,
        field: Optional[str] = None,
        value: Optional[str] = None,
        recommendation: Optional[str] = None,
        next_step: Optional[str] = None,
        caution: Optional[str] = None,
    ) -> Dict[str, Any]:

        payload = {
            "category": category,
            "severity": severity,
            "title": title,
            "basis": basis,
            "field": field,
            "value": value,
            "rows": affected_rows or [],
        }

        finding = {
            "id": make_id("F", payload),
            "category": category,
            "severity": severity,
            "title": title,
            "status": STATUS_OPEN,
            "basis": basis,
            "evidence_score": round(clamp(evidence_score), 3),
            "field": field,
            "value": value,
            "affected_rows": affected_rows or [],
            "recommendation": recommendation,
            "next_step": next_step,
            "caution": caution,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "verification": {
                "required": True,
                "status": "PENDING",
                "verified_at": None,
                "result": None,
            },
        }

        self.findings.append(finding)

        self.add_audit(
            "FINDING_CREATED",
            title,
            {
                "finding_id": finding["id"],
                "category": category,
                "severity": severity,
                "evidence_score": finding["evidence_score"],
            },
        )

        return finding

    # --------------------------------------------------------
    # OBSERVATION
    # --------------------------------------------------------

    def observe(self) -> Dict[str, Any]:
        fields = self.dataset.fields
        rows = self.dataset.rows

        total_cells = len(fields) * len(rows)

        missing_cells = sum(
            1
            for row in rows
            for field in fields
            if is_missing(row.get(field))
        )

        completeness = (
            1 - (missing_cells / total_cells)
            if total_cells
            else 0.0
        )

        row_scores = [
            row_completeness(row, fields)
            for row in rows
        ]

        observation = {
            "row_count": len(rows),
            "field_count": len(fields),
            "fields": fields,
            "total_cells": total_cells,
            "missing_cells": missing_cells,
            "completeness": round(completeness, 4),
            "row_completeness": {
                "min": round(min(row_scores), 4) if row_scores else 0.0,
                "max": round(max(row_scores), 4) if row_scores else 0.0,
                "mean": round(
                    sum(row_scores) / len(row_scores), 4
                ) if row_scores else 0.0,
            },
        }

        self.add_audit(
            "OBSERVATION_COMPLETE",
            "Dataset observation completed",
            observation,
        )

        return observation

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    def structure(self) -> Dict[str, Any]:
        fields = self.dataset.fields
        rows = self.dataset.rows

        field_info = {}

        for field in fields:
            values = [
                row.get(field, "")
                for row in rows
                if not is_missing(row.get(field))
            ]

            unique = len(set(values))

            field_info[field] = {
                "kind": field_kind(field),
                "observed": len(values),
                "missing": len(rows) - len(values),
                "unique": unique,
                "uniqueness_ratio": round(
                    unique / len(values), 4
                ) if values else 0.0,
            }

        result = {
            "fields": fields,
            "field_info": field_info,
        }

        self.add_audit(
            "STRUCTURE_COMPLETE",
            "Dataset structure assessed",
            {"field_count": len(fields)},
        )

        return result

    # --------------------------------------------------------
    # VALIDITY
    # --------------------------------------------------------

    def validity(self) -> Dict[str, Any]:
        result = {}

        for field in self.dataset.fields:
            kind = field_kind(field)

            valid = 0
            invalid = 0
            missing = 0
            placeholder = 0
            invalid_rows = []
            placeholder_rows = []

            for idx, row in enumerate(self.dataset.rows, start=1):
                value = row.get(field, "")

                if is_missing(value):
                    missing += 1
                    continue

                if looks_like_placeholder(value):
                    placeholder += 1
                    placeholder_rows.append(idx)

                ok, _ = validate_value(kind, value)

                if ok:
                    valid += 1
                else:
                    invalid += 1
                    invalid_rows.append(idx)

            result[field] = {
                "kind": kind,
                "valid": valid,
                "invalid": invalid,
                "missing": missing,
                "placeholder": placeholder,
                "invalid_rows": invalid_rows,
                "placeholder_rows": placeholder_rows,
            }

            if invalid:
                self.add_finding(
                    "FIELD_VALIDITY",
                    "HIGH",
                    f"Review {invalid} structurally invalid value(s) in '{field}'",
                    (
                        f"AEGIS found {invalid} value(s) in '{field}' "
                        f"that fail the basic {kind} format check."
                    ),
                    clamp(0.70 + min(invalid / max(len(self.dataset.rows), 1), 0.20)),
                    affected_rows=invalid_rows,
                    field=field,
                    recommendation=(
                        f"Review invalid values in '{field}' before relying "
                        "on this field."
                    ),
                    next_step=(
                        "Inspect each affected record and correct or verify "
                        "the value."
                    ),
                    caution=(
                        "Format validation does not prove that a value is "
                        "real, reachable, or associated with the intended entity."
                    ),
                )

            if placeholder:
                counts = Counter(
                    self.dataset.rows[i - 1].get(field, "")
                    for i in placeholder_rows
                )

                for value, count in counts.items():
                    rows_for_value = [
                        i
                        for i in placeholder_rows
                        if self.dataset.rows[i - 1].get(field, "") == value
                    ]

                    self.add_finding(
                        "PLACEHOLDER_REVIEW",
                        "HIGH",
                        f"Review possible placeholder '{value}' in '{field}'",
                        (
                            f"The value appears {count} time(s) and matches "
                            "AEGIS's conservative placeholder indicators."
                        ),
                        clamp(
                            0.60 +
                            min(
                                count / max(len(self.dataset.rows), 1),
                                0.30,
                            )
                        ),
                        affected_rows=rows_for_value,
                        field=field,
                        value=value,
                        recommendation=(
                            f"Confirm whether '{value}' represents real "
                            "information or a default/test value."
                        ),
                        next_step=(
                            "Inspect the targeted records and establish "
                            "the value's intended meaning."
                        ),
                        caution=(
                            "AEGIS cannot determine from the value alone "
                            "whether it is legitimate."
                        ),
                    )

        self.add_audit(
            "VALIDITY_COMPLETE",
            "Field validity assessment completed",
            {"fields_assessed": len(result)},
        )

        return result

    # --------------------------------------------------------
    # MISSINGNESS
    # --------------------------------------------------------

    def missingness(self) -> Dict[str, Any]:
        rows = self.dataset.rows
        fields = self.dataset.fields

        field_missing = {}

        for field in fields:
            count = sum(
                1
                for row in rows
                if is_missing(row.get(field))
            )

            field_missing[field] = count

            if rows and count == len(rows):
                self.add_finding(
                    "DATA_QUALITY",
                    "HIGH",
                    f"Review the '{field}' field before relying on it",
                    (
                        f"0 of {len(rows)} observations contain a "
                        "usable value in this field."
                    ),
                    0.900,
                    field=field,
                    recommendation=(
                        f"Verify whether '{field}' should be collected, "
                        "populated, or removed."
                    ),
                    next_step=(
                        "Determine whether the field is intentionally unused "
                        "or whether collection/population failed."
                    ),
                    caution=(
                        "The field may be intentionally unused; "
                        "AEGIS cannot determine why it is empty."
                    ),
                )

            elif rows and count / len(rows) >= 0.50:
                ratio = count / len(rows)

                self.add_finding(
                    "DATA_QUALITY",
                    "HIGH",
                    f"Review missing data in '{field}'",
                    (
                        f"{count} of {len(rows)} observations "
                        f"({ratio:.1%}) are missing."
                    ),
                    clamp(0.70 + ratio * 0.25),
                    field=field,
                    recommendation=(
                        f"Determine why '{field}' is missing and whether "
                        "the field can be reliably completed."
                    ),
                    next_step=(
                        "Identify the source or collection condition "
                        "responsible for the missing values."
                    ),
                    caution=(
                        "Missingness does not by itself mean the records "
                        "are invalid."
                    ),
                )

        # Row quality
        low_rows = [
            idx
            for idx, row in enumerate(rows, start=1)
            if row_completeness(row, fields) < 0.50
        ]

        if low_rows:
            score = len(low_rows) / max(len(rows), 1)

            self.add_finding(
                "ROW_QUALITY",
                "HIGH",
                f"Review {len(low_rows)} record(s) with less than 50% completeness",
                (
                    f"{len(low_rows)} of {len(rows)} records are less "
                    "than half populated."
                ),
                1.0,
                affected_rows=low_rows,
                recommendation=(
                    "Inspect the lowest-completeness records and determine "
                    "whether their missing fields are expected."
                ),
                next_step=(
                    "Classify each sparse record as expected, incomplete, "
                    "or requiring correction."
                ),
                caution=(
                    "A sparse record is not automatically invalid."
                ),
            )

        # Pairwise missingness relationships
        pairs = []

        for i, a in enumerate(fields):
            for b in fields[i + 1:]:
                both = sum(
                    1
                    for row in rows
                    if is_missing(row.get(a))
                    and is_missing(row.get(b))
                )

                a_missing = sum(
                    1
                    for row in rows
                    if is_missing(row.get(a))
                )

                b_missing = sum(
                    1
                    for row in rows
                    if is_missing(row.get(b))
                )

                if both and min(a_missing, b_missing) > 0:
                    overlap = both / min(a_missing, b_missing)

                    if overlap >= 0.70:
                        pairs.append({
                            "field_a": a,
                            "field_b": b,
                            "both_missing": both,
                            "overlap": round(overlap, 4),
                        })

                        self.add_finding(
                            "MISSINGNESS_PATTERN",
                            "MEDIUM",
                            f"Investigate why '{a}' and '{b}' are often missing together",
                            (
                                f"Both fields are missing in {both} "
                                f"observations "
                                f"(missingness overlap={overlap:.3f})."
                            ),
                            clamp(0.60 + overlap * 0.34),
                            field=f"{a} <-> {b}",
                            recommendation=(
                                f"Check whether '{a}' and '{b}' come from "
                                "the same source, collection step, or "
                                "eligibility condition."
                            ),
                            next_step=(
                                "Trace the shared missingness condition "
                                "before attempting completion."
                            ),
                            caution=(
                                "Co-missing fields do not establish "
                                "the reason for the missingness."
                            ),
                        )

        return {
            "field_missing": field_missing,
            "paired_missingness": pairs,
        }

    # --------------------------------------------------------
    # CONCENTRATION
    # --------------------------------------------------------

    def concentration(self) -> List[Dict[str, Any]]:
        results = []

        for field in self.dataset.fields:
            values = [
                normalize_value(row.get(field))
                for row in self.dataset.rows
                if not is_missing(row.get(field))
            ]

            if not values:
                continue

            counts = Counter(values)

            for value, count in counts.most_common():
                ratio = count / len(values)

                if count >= 4 and ratio >= 0.50:
                    rows = [
                        idx
                        for idx, row in enumerate(
                            self.dataset.rows,
                            start=1,
                        )
                        if normalize_value(row.get(field)) == value
                    ]

                    results.append({
                        "field": field,
                        "value": value,
                        "count": count,
                        "observed": len(values),
                        "ratio": round(ratio, 4),
                        "rows": rows,
                    })

                    self.add_finding(
                        "CONCENTRATION",
                        "MEDIUM",
                        f"Review records containing '{value}' in '{field}'",
                        (
                            f"{count} of {len(values)} observations "
                            f"({ratio:.1%}) contain this value."
                        ),
                        clamp(0.50 + ratio * 0.45),
                        affected_rows=rows,
                        field=field,
                        value=value,
                        recommendation=(
                            f"Check whether '{value}' represents a "
                            "legitimate category or a default value."
                        ),
                        next_step=(
                            "Inspect the affected records and compare "
                            "the value with the intended field semantics."
                        ),
                        caution=(
                            "High frequency does not prove that the value "
                            "is correct or incorrect."
                        ),
                    )

        return results

    # --------------------------------------------------------
    # DUPLICATES
    # --------------------------------------------------------

    def duplicates(self) -> Dict[str, Any]:
        rows = self.dataset.rows

        exact_groups = defaultdict(list)

        for idx, row in enumerate(rows, start=1):
            key = tuple(
                normalize_value(row.get(field))
                for field in self.dataset.fields
            )
            exact_groups[key].append(idx)

        exact = [
            {
                "rows": group,
                "count": len(group),
            }
            for group in exact_groups.values()
            if len(group) > 1
        ]

        identity_groups = defaultdict(list)

        identity_fields = [
            f
            for f in self.dataset.fields
            if field_kind(f) in {"email", "phone"}
        ]

        for idx, row in enumerate(rows, start=1):
            parts = []

            for field in identity_fields:
                value = normalize_value(row.get(field)).lower()

                if value and not looks_like_placeholder(value):
                    parts.append((field, value))

            if parts:
                identity_groups[tuple(parts)].append(idx)

        identity_repeated = [
            {
                "identity": dict(key),
                "rows": group,
                "count": len(group),
            }
            for key, group in identity_groups.items()
            if len(group) > 1
        ]

        for group in exact:
            self.add_finding(
                "DUPLICATE_REVIEW",
                "HIGH",
                "Review exact duplicate records",
                (
                    f"The exact same complete row occurs "
                    f"{group['count']} times."
                ),
                0.98,
                affected_rows=group["rows"],
                recommendation="Determine whether the repeated rows are intentional.",
                next_step="Retain one record only if duplicate status is verified.",
                caution="Repeated rows may be legitimate repeated observations.",
            )

        for group in identity_repeated:
            self.add_finding(
                "IDENTITY_REVIEW",
                "MEDIUM",
                "Review repeated identity-like values",
                (
                    f"The same identity-like value combination occurs "
                    f"{group['count']} times."
                ),
                0.85,
                affected_rows=group["rows"],
                recommendation="Determine whether the records represent separate entities.",
                next_step="Compare the remaining fields before merging or retaining.",
                caution="Identity-like repetition does not prove duplication.",
            )

        return {
            "exact_duplicate_groups": exact,
            "exact_rows_involved": sum(
                len(x["rows"]) for x in exact
            ),
            "identity_repeated_groups": identity_repeated,
        }

    # --------------------------------------------------------
    # FIELD COMBINATIONS
    # --------------------------------------------------------

    def field_combinations(self) -> List[Dict[str, Any]]:
        results = []

        if len(self.dataset.fields) < 2:
            return results

        # Pair combinations only; keeps analysis deterministic.
        for i, field_a in enumerate(self.dataset.fields):
            for field_b in self.dataset.fields[i + 1:]:
                combos = defaultdict(list)

                for idx, row in enumerate(
                    self.dataset.rows,
                    start=1,
                ):
                    a = normalize_value(row.get(field_a))
                    b = normalize_value(row.get(field_b))

                    if not a or not b:
                        continue

                    combos[(a, b)].append(idx)

                for (a, b), row_ids in combos.items():
                    if len(row_ids) >= 3:
                        results.append({
                            "field_a": field_a,
                            "value_a": a,
                            "field_b": field_b,
                            "value_b": b,
                            "count": len(row_ids),
                            "rows": row_ids,
                        })

                        self.add_finding(
                            "FIELD_COMBINATION",
                            "MEDIUM",
                            (
                                f"Review recurring combination "
                                f"{field_a}={a} <-> "
                                f"{field_b}={b}"
                            ),
                            (
                                f"The combination appears "
                                f"{len(row_ids)} times."
                            ),
                            clamp(
                                0.45 +
                                min(
                                    len(row_ids) /
                                    max(len(self.dataset.rows), 1),
                                    0.45,
                                )
                            ),
                            affected_rows=row_ids,
                            recommendation=(
                                "Inspect whether the repeated combination "
                                "represents a legitimate category, default, "
                                "or repeated entity."
                            ),
                            next_step=(
                                "Compare the remaining fields for the "
                                "affected records."
                            ),
                            caution=(
                                "Repeated combinations do not prove that "
                                "the records are duplicates."
                            ),
                        )

        return results

    # --------------------------------------------------------
    # ANOMALIES
    # --------------------------------------------------------

    def anomalies(self) -> List[Dict[str, Any]]:
        results = []

        for field in self.dataset.fields:
            values = [
                normalize_value(row.get(field))
                for row in self.dataset.rows
                if not is_missing(row.get(field))
            ]

            if len(values) < 5:
                continue

            counts = Counter(values)

            # Rare values are only flagged when the field has enough
            # observations and there is meaningful concentration.
            rare = [
                (value, count)
                for value, count in counts.items()
                if count == 1
            ]

            dominant = max(counts.values())

            if dominant >= 5 and rare:
                rare_rows = []

                for value, _ in rare:
                    rare_rows.extend(
                        idx
                        for idx, row in enumerate(
                            self.dataset.rows,
                            start=1,
                        )
                        if normalize_value(row.get(field)) == value
                    )

                result = {
                    "field": field,
                    "rare_values": len(rare),
                    "dominant_count": dominant,
                    "rows": rare_rows,
                }

                results.append(result)

                self.add_finding(
                    "ANOMALY_REVIEW",
                    "LOW",
                    f"Review rare values in '{field}'",
                    (
                        f"The field contains {len(rare)} value(s) "
                        f"appearing once while the dominant value occurs "
                        f"{dominant} times."
                    ),
                    0.55,
                    affected_rows=rare_rows,
                    field=field,
                    recommendation=(
                        f"Inspect unusually rare '{field}' values for "
                        "unexpected entry patterns."
                    ),
                    next_step=(
                        "Compare rare records with surrounding records "
                        "and field semantics."
                    ),
                    caution=(
                        "Rarity alone does not establish an error."
                    ),
                )

        return results

    # --------------------------------------------------------
    # EVIDENCE
    # --------------------------------------------------------

    def evidence(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        row_count = observation["row_count"]
        field_count = observation["field_count"]

        structural_signals = len(self.findings)

        strong_signals = sum(
            1
            for finding in self.findings
            if finding["severity"] == "HIGH"
            and finding["evidence_score"] >= 0.80
        )

        coverage = (
            1 - observation["missing_cells"] /
            max(observation["total_cells"], 1)
        )

        signal_component = clamp(
            structural_signals / max(
                row_count + field_count,
                1,
            )
        )

        strong_component = clamp(
            strong_signals / max(
                structural_signals,
                1,
            )
        )

        evidence_score = clamp(
            0.40 * coverage +
            0.35 * signal_component +
            0.25 * strong_component
        )

        if evidence_score >= 0.75:
            level = "HIGH"
        elif evidence_score >= 0.50:
            level = "MODERATE"
        else:
            level = "LOW"

        result = {
            "level": level,
            "score": round(evidence_score, 3),
            "coverage": round(coverage, 3),
            "structural_signals": structural_signals,
            "strong_signals": strong_signals,
        }

        self.add_audit(
            "EVIDENCE_COMPLETE",
            "Evidence assessment completed",
            result,
        )

        return result

    # --------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------

    def prioritize(self) -> List[Dict[str, Any]]:
        severity_weight = {
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1,
        }

        for finding in self.findings:
            severity = severity_weight.get(
                finding["severity"],
                1,
            )

            evidence = finding["evidence_score"]

            affected = len(
                finding.get("affected_rows", [])
            )

            impact = clamp(
                affected /
                max(len(self.dataset.rows), 1)
            )

            priority_score = (
                0.45 * (severity / 3)
                + 0.40 * evidence
                + 0.15 * impact
            )

            finding["priority_score"] = round(
                priority_score,
                3,
            )

            if priority_score >= 0.75:
                finding["priority"] = "HIGH"
            elif priority_score >= 0.50:
                finding["priority"] = "MEDIUM"
            else:
                finding["priority"] = "LOW"

        self.findings.sort(
            key=lambda x: (
                -x["priority_score"],
                x["id"],
            )
        )

        return self.findings

    # --------------------------------------------------------
    # ACTION QUEUE
    # --------------------------------------------------------

    def build_action_queue(self) -> List[Dict[str, Any]]:
        queue = []

        for position, finding in enumerate(
            self.findings,
            start=1,
        ):
            action = {
                "queue_position": position,
                "finding_id": finding["id"],
                "priority": finding["priority"],
                "severity": finding["severity"],
                "action": finding["next_step"],
                "rows": finding["affected_rows"],
                "status": "PENDING",
                "created_at": now_iso(),
            }

            queue.append(action)

        self.actions = queue

        self.add_audit(
            "ACTION_QUEUE_CREATED",
            "Action queue constructed",
            {
                "actions": len(queue),
            },
        )

        return queue

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    def analyze(self) -> Dict[str, Any]:
        observation = self.observe()
        structure = self.structure()
        validity = self.validity()
        missingness = self.missingness()
        concentration = self.concentration()
        duplicates = self.duplicates()
        combinations = self.field_combinations()
        anomalies = self.anomalies()

        evidence = self.evidence(observation)
        findings = self.prioritize()
        action_queue = self.build_action_queue()

        self.add_audit(
            "ANALYSIS_COMPLETE",
            "Initial AEGIS analysis completed",
            {
                "findings": len(findings),
                "actions": len(action_queue),
            },
        )

        self.report = {
            "aegis": {
                "name": "AEGIS",
                "version": VERSION,
                "run_id": str(uuid.uuid4()),
                "timestamp": now_iso(),
                "mode": "ANALYSIS",
            },

            "source": self.dataset.snapshot(),

            "observation": observation,

            "structure": structure,

            "validity": validity,

            "missingness": missingness,

            "concentration": concentration,

            "duplicates": duplicates,

            "field_combinations": combinations,

            "anomalies": anomalies,

            "evidence": evidence,

            "findings": findings,

            "action_queue": action_queue,

            "resolution": {
                "open": len(findings),
                "in_progress": 0,
                "resolved": 0,
                "verified": 0,
                "dismissed": 0,
                "reopened": 0,
                "closure": "NOT_CLOSED",
            },

            "verification": {
                "required": len(findings) > 0,
                "status": "PENDING",
                "last_verified_at": None,
                "source_hash_at_verification": None,
                "verified_findings": [],
                "failed_findings": [],
                "reopened_findings": [],
            },

            "audit": self.audit,

            "integrity": {},
        }

        self.finalize_integrity()

        return self.report

    # --------------------------------------------------------
    # ACTION RECORDING
    # --------------------------------------------------------

    def record_action(
        self,
        finding_id: str,
        action: str,
        result: str,
        status: str = STATUS_IN_PROGRESS,
        actor: str = "USER",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        finding = next(
            (
                f
                for f in self.findings
                if f["id"] == finding_id
            ),
            None,
        )

        if finding is None:
            raise ValueError(
                f"Finding not found: {finding_id}"
            )

        event = {
            "action_id": str(uuid.uuid4()),
            "finding_id": finding_id,
            "timestamp": now_iso(),
            "actor": actor,
            "action": action,
            "result": result,
            "status": status,
            "details": details or {},
        }

        self.audit.append({
            "timestamp": event["timestamp"],
            "event": "ACTION_RECORDED",
            "description": action,
            "details": event,
        })

        finding["status"] = status
        finding["updated_at"] = now_iso()

        if status in {
            STATUS_RESOLVED,
            STATUS_DISMISSED,
        }:
            finding["verification"]["status"] = "PENDING"

        return event

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def verify_against(
        self,
        new_dataset: Dataset,
    ) -> Dict[str, Any]:

        old_findings = {
            finding["id"]: finding
            for finding in self.findings
        }

        fresh = AEGIS(new_dataset)
        new_report = fresh.analyze()

        verification = {
            "verified_at": now_iso(),
            "source_hash_at_verification": sha256_file(
                new_dataset.source
            ),
            "verified_findings": [],
            "failed_findings": [],
            "reopened_findings": [],
            "new_findings": [],
        }

        # Match findings by semantic signature.
        old_signatures = {}

        for finding in self.findings:
            signature = (
                finding["category"],
                finding.get("field"),
                finding.get("value"),
            )
            old_signatures[signature] = finding

        new_signatures = {}

        for finding in fresh.findings:
            signature = (
                finding["category"],
                finding.get("field"),
                finding.get("value"),
            )
            new_signatures[signature] = finding

        for signature, old in old_signatures.items():

            if signature not in new_signatures:
                old["verification"] = {
                    "required": True,
                    "status": "VERIFIED",
                    "verified_at": verification["verified_at"],
                    "result": "FINDING_NO_LONGER_DETECTED",
                }

                if old["status"] != STATUS_DISMISSED:
                    old["status"] = STATUS_VERIFIED

                verification["verified_findings"].append(
                    old["id"]
                )

            else:
                new = new_signatures[signature]

                if (
                    new["evidence_score"]
                    < old["evidence_score"]
                    or
                    len(new.get("affected_rows", []))
                    < len(old.get("affected_rows", []))
                ):
                    old["verification"] = {
                        "required": True,
                        "status": "PARTIAL",
                        "verified_at": verification["verified_at"],
                        "result": {
                            "previous_rows": len(
                                old.get("affected_rows", [])
                            ),
                            "current_rows": len(
                                new.get("affected_rows", [])
                            ),
                            "previous_evidence": old[
                                "evidence_score"
                            ],
                            "current_evidence": new[
                                "evidence_score"
                            ],
                        },
                    }

                    verification["failed_findings"].append(
                        old["id"]
                    )

                else:
                    old["verification"] = {
                        "required": True,
                        "status": "REOPENED",
                        "verified_at": verification["verified_at"],
                        "result": "FINDING_STILL_PRESENT",
                    }

                    old["status"] = STATUS_REOPENED

                    verification["reopened_findings"].append(
                        old["id"]
                    )

        for signature, new in new_signatures.items():
            if signature not in old_signatures:
                verification["new_findings"].append(
                    new["id"]
                )

        verified_count = len(
            verification["verified_findings"]
        )

        failed_count = len(
            verification["failed_findings"]
        )

        reopened_count = len(
            verification["reopened_findings"]
        )

        total_old = len(old_findings)

        if total_old == 0:
            verification["status"] = "NO_FINDINGS"
        elif (
            verified_count == total_old
            and reopened_count == 0
        ):
            verification["status"] = "PASS"
        elif verified_count > 0:
            verification["status"] = "PARTIAL"
        else:
            verification["status"] = "FAIL"

        self.report["verification"] = verification

        self.recalculate_resolution()

        self.add_audit(
            "VERIFICATION_COMPLETE",
            "Fresh dataset verification completed",
            verification,
        )

        self.finalize_integrity()

        return verification

    # --------------------------------------------------------
    # RESOLUTION
    # --------------------------------------------------------

    def recalculate_resolution(self) -> Dict[str, Any]:
        counts = Counter(
            finding["status"]
            for finding in self.findings
        )

        resolution = {
            "open": counts[STATUS_OPEN],
            "in_progress": counts[STATUS_IN_PROGRESS],
            "resolved": counts[STATUS_RESOLVED],
            "verified": counts[STATUS_VERIFIED],
            "dismissed": counts[STATUS_DISMISSED],
            "reopened": counts[STATUS_REOPENED],
            "closure": "NOT_CLOSED",
        }

        unresolved = (
            resolution["open"]
            + resolution["in_progress"]
            + resolution["reopened"]
        )

        if not self.findings:
            resolution["closure"] = "CLOSED_NO_FINDINGS"

        elif unresolved == 0:
            resolution["closure"] = "CLOSED"

        else:
            resolution["closure"] = "OPEN"

        self.report["resolution"] = resolution

        return resolution

    # --------------------------------------------------------
    # INTEGRITY
    # --------------------------------------------------------

    def finalize_integrity(self) -> None:
        # Exclude integrity itself from the hash.
        report_copy = dict(self.report)
        report_copy["integrity"] = {}

        digest = sha256_text(
            stable_json(report_copy)
        )

        self.report["integrity"] = {
            "algorithm": "SHA-256",
            "report_hash": digest,
        }

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    def save(self, output: Path) -> None:
        self.recalculate_resolution()
        self.finalize_integrity()

        output.write_text(
            json.dumps(
                self.report,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.add_audit(
            "REPORT_SAVED",
            "Machine-readable report saved",
            {
                "path": str(output),
                "sha256": sha256_file(output),
            },
        )

        # Save audit update.
        self.report["audit"] = self.audit
        self.finalize_integrity()

        output.write_text(
            json.dumps(
                self.report,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    # --------------------------------------------------------
    # HUMAN REPORT
    # --------------------------------------------------------

    def human_report(self) -> str:
        r = self.report

        obs = r["observation"]
        ev = r["evidence"]
        dup = r["duplicates"]
        resolution = r["resolution"]

        lines = []

        lines.append("=" * 65)
        lines.append(f"AEGIS {VERSION}")
        lines.append(
            "OBSERVATION -> STRUCTURE -> VALIDITY -> EVIDENCE"
        )
        lines.append(
            "-> RECOMMENDATION -> ACTION -> VERIFICATION"
        )
        lines.append("=" * 65)
        lines.append("")

        lines.append("RESULT")
        lines.append(f"File: {self.dataset.source}")
        lines.append(f"Observations: {obs['row_count']}")
        lines.append(f"Variables: {obs['field_count']}")
        lines.append("")

        lines.append("DATA QUALITY")
        lines.append(
            f"Completeness: {obs['completeness']:.1%}"
        )
        lines.append(
            f"Missing cells: {obs['missing_cells']}"
        )
        lines.append("")

        lines.append("EVIDENCE ASSESSMENT")
        lines.append(
            f"Evidence level: {ev['level']}"
        )
        lines.append(
            f"Evidence score: {ev['score']:.3f}"
        )
        lines.append(
            f"Coverage: {ev['coverage']:.3f}"
        )
        lines.append(
            f"Structural signals: {ev['structural_signals']}"
        )
        lines.append(
            f"Strong signals: {ev['strong_signals']}"
        )
        lines.append("")

        lines.append("VALIDITY")

        for field, data in r["validity"].items():
            lines.append(
                f"  {field}: "
                f"valid={data['valid']} "
                f"invalid={data['invalid']} "
                f"missing={data['missing']} "
                f"placeholder={data['placeholder']}"
            )

        lines.append("")

        lines.append("DUPLICATES")
        lines.append(
            f"Exact duplicate groups: "
            f"{len(dup['exact_duplicate_groups'])}"
        )
        lines.append(
            f"Rows involved: "
            f"{dup['exact_rows_involved']}"
        )
        lines.append(
            f"Identity-like repeated groups: "
            f"{len(dup['identity_repeated_groups'])}"
        )
        lines.append("")

        if r["missingness"]["paired_missingness"]:
            lines.append("MISSINGNESS PATTERNS")

            for item in r["missingness"]["paired_missingness"]:
                lines.append(
                    f"  {item['field_a']} <-> "
                    f"{item['field_b']} "
                    f"(both missing={item['both_missing']}, "
                    f"overlap={item['overlap']:.3f})"
                )

            lines.append("")

        lines.append("FINDINGS")

        if not r["findings"]:
            lines.append("  None.")
        else:
            for i, finding in enumerate(
                r["findings"],
                start=1,
            ):
                lines.append(
                    f"  [{i}] "
                    f"{finding['priority']} "
                    f"{finding['category']}"
                )
                lines.append(
                    f"      {finding['title']}"
                )
                lines.append(
                    f"      Evidence: "
                    f"{finding['evidence_score']:.3f}"
                )
                lines.append(
                    f"      Status: "
                    f"{finding['status']}"
                )

                rows = finding.get("affected_rows", [])

                if rows:
                    lines.append(
                        f"      Rows: "
                        f"{', '.join(map(str, rows))}"
                    )

        lines.append("")

        lines.append("ACTION QUEUE")

        if not r["action_queue"]:
            lines.append("  None.")
        else:
            for action in r["action_queue"]:
                lines.append(
                    f"  [{action['queue_position']}] "
                    f"{action['priority']} "
                    f"{action['finding_id']}"
                )
                lines.append(
                    f"      {action['action']}"
                )

        lines.append("")

        lines.append("RESOLUTION")
        lines.append(
            f"  OPEN: {resolution['open']}"
        )
        lines.append(
            f"  IN_PROGRESS: {resolution['in_progress']}"
        )
        lines.append(
            f"  RESOLVED: {resolution['resolved']}"
        )
        lines.append(
            f"  VERIFIED: {resolution['verified']}"
        )
        lines.append(
            f"  DISMISSED: {resolution['dismissed']}"
        )
        lines.append(
            f"  REOPENED: {resolution['reopened']}"
        )
        lines.append(
            f"  CLOSURE: {resolution['closure']}"
        )

        lines.append("")

        verification = r["verification"]

        lines.append("VERIFICATION")
        lines.append(
            f"  Status: {verification['status']}"
        )
        lines.append(
            f"  Verified findings: "
            f"{len(verification['verified_findings'])}"
        )
        lines.append(
            f"  Failed findings: "
            f"{len(verification['failed_findings'])}"
        )
        lines.append(
            f"  Reopened findings: "
            f"{len(verification['reopened_findings'])}"
        )
        lines.append(
            f"  New findings: "
            f"{len(verification.get('new_findings', []))}"
        )

        lines.append("")

        lines.append("INTEGRITY")
        lines.append(
            f"  Algorithm: "
            f"{r['integrity']['algorithm']}"
        )
        lines.append(
            f"  Report hash: "
            f"{r['integrity']['report_hash']}"
        )

        lines.append("")
        lines.append("=" * 65)
        lines.append(f"AEGIS {VERSION} ANALYSIS COMPLETE")
        lines.append("=" * 65)

        return "\n".join(lines)


# ============================================================
# COMMANDS
# ============================================================

def command_analyze(args: argparse.Namespace) -> int:
    source = Path(args.file).expanduser().resolve()

    if not source.exists():
        print(f"ERROR: File does not exist: {source}")
        return 1

    if not source.is_file():
        print(f"ERROR: Not a file: {source}")
        return 1

    try:
        dataset = Dataset.load_csv(source)
        engine = AEGIS(dataset)
        engine.analyze()

        output = (
            Path(args.output).expanduser().resolve()
            if args.output
            else source.with_suffix(".aegis.json")
        )

        engine.save(output)

        print()
        print(engine.human_report())
        print()
        print(f"Report saved: {output}")

        return 0

    except Exception as exc:
        print(
            f"AEGIS ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


def command_verify(args: argparse.Namespace) -> int:
    original = Path(args.report).expanduser().resolve()
    fresh_source = Path(args.file).expanduser().resolve()

    if not original.exists():
        print(f"ERROR: Report does not exist: {original}")
        return 1

    if not fresh_source.exists():
        print(f"ERROR: File does not exist: {fresh_source}")
        return 1

    try:
        report = json.loads(
            original.read_text(
                encoding="utf-8"
            )
        )

        source_path = Path(
            report["source"]["source"]
        )

        if not source_path.exists():
            print(
                "ERROR: Original source referenced by the report "
                f"does not exist: {source_path}"
            )
            return 1

        original_dataset = Dataset.load_csv(
            source_path
        )

        engine = AEGIS(original_dataset)

        # Restore original findings.
        engine.findings = report.get(
            "findings",
            [],
        )

        engine.report = report

        new_dataset = Dataset.load_csv(
            fresh_source
        )

        result = engine.verify_against(
            new_dataset
        )

        engine.save(original)

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        print()
        print(
            f"Verification report updated: {original}"
        )

        return 0

    except Exception as exc:
        print(
            f"AEGIS VERIFY ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


def command_status(args: argparse.Namespace) -> int:
    report_path = Path(args.report).expanduser().resolve()

    if not report_path.exists():
        print(
            f"ERROR: Report does not exist: {report_path}"
        )
        return 1

    try:
        report = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )

        print("=" * 65)
        print("AEGIS STATUS")
        print("=" * 65)

        print(
            f"Version: {report['aegis']['version']}"
        )
        print(
            f"Run ID: {report['aegis']['run_id']}"
        )
        print(
            f"Source: {report['source']['source']}"
        )
        print(
            f"Source SHA-256: {report['source']['sha256']}"
        )

        resolution = report.get(
            "resolution",
            {},
        )

        print()
        print("RESOLUTION")
        print(
            f"Open: {resolution.get('open', 0)}"
        )
        print(
            f"In progress: "
            f"{resolution.get('in_progress', 0)}"
        )
        print(
            f"Resolved: "
            f"{resolution.get('resolved', 0)}"
        )
        print(
            f"Verified: "
            f"{resolution.get('verified', 0)}"
        )
        print(
            f"Dismissed: "
            f"{resolution.get('dismissed', 0)}"
        )
        print(
            f"Reopened: "
            f"{resolution.get('reopened', 0)}"
        )
        print(
            f"Closure: "
            f"{resolution.get('closure', 'UNKNOWN')}"
        )

        verification = report.get(
            "verification",
            {},
        )

        print()
        print("VERIFICATION")
        print(
            f"Status: "
            f"{verification.get('status', 'PENDING')}"
        )

        print()
        print(
            f"Findings: "
            f"{len(report.get('findings', []))}"
        )
        print(
            f"Actions: "
            f"{len(report.get('action_queue', []))}"
        )

        print("=" * 65)

        return 0

    except Exception as exc:
        print(
            f"AEGIS STATUS ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aegis",
        description=(
            "AEGIS — evidence-grounded dataset "
            "inspection and verification system."
        ),
    )

    sub = parser.add_subparsers(
        dest="command"
    )

    analyze = sub.add_parser(
        "analyze",
        help="Analyze a CSV.",
    )

    analyze.add_argument(
        "file",
        help="CSV file to analyze.",
    )

    analyze.add_argument(
        "-o",
        "--output",
        help="Output JSON report path.",
    )

    analyze.set_defaults(
        handler=command_analyze
    )

    verify = sub.add_parser(
        "verify",
        help="Verify an existing report against a fresh CSV.",
    )

    verify.add_argument(
        "report",
        help="Existing .aegis.json report.",
    )

    verify.add_argument(
        "file",
        help="Fresh CSV to verify against.",
    )

    verify.set_defaults(
        handler=command_verify
    )

    status = sub.add_parser(
        "status",
        help="Show report lifecycle status.",
    )

    status.add_argument(
        "report",
        help="AEGIS JSON report.",
    )

    status.set_defaults(
        handler=command_status
    )

    return parser


def main() -> int:
    parser = build_parser()

    # Preserve the simple syntax:
    # aegis file.csv
    #
    # by translating it into:
    # aegis analyze file.csv
    if len(sys.argv) >= 2:
        first = sys.argv[1]

        if (
            not first.startswith("-")
            and first not in {
                "analyze",
                "verify",
                "status",
                "-h",
                "--help",
            }
        ):
            sys.argv.insert(1, "analyze")

    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
