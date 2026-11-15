"""The "no new numbers" check: every number in an AI report must come from its input.

Allowed: any number found in the input (as a value or inside a string), its usual roundings, the
percent form of shares (0.35 -> 35), and a few small counts (0-5 strategies, 12 months).
Decimal commas and thousands separators are both accepted ("74,8", "2,721"), but a whole
thousands group is never a decimal ("50,000" is 50000, not 50.0), and "50 000" is one number.
"""

from __future__ import annotations

import math
import re
from typing import Any

FREE = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 12.0}
_SPACES = " \u00a0\u202f"  # "50 000" with a space, no-break or narrow no-break space
_IN_REPORT = re.compile(  # skips digits inside words (MOD13Q1)
    rf"(?<![\w.,])(?:\d{{1,3}}(?:[{_SPACES}]\d{{3}})+(?![\w.,])|\d+(?:[.,]\d+)*)")
_GROUPED = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _variants(x: float) -> set[float]:
    out = {x, abs(x)}
    for v in (x, abs(x)) if abs(x) > 1 else (x, abs(x), abs(x) * 100):
        out |= {round(v), round(v, 1), round(v, 2)}
    return {round(float(v), 4) for v in out}


def _readings(token: str) -> set[float]:
    """Every way the token could be read: 2,721 -> 2721 or 2.721; 74,8 -> 74.8 or 748."""
    token = re.sub(f"[{_SPACES}]", "", token)
    out = set()
    for candidate in (token.replace(",", ""), token.replace(".", "").replace(",", "."),
                      token.replace(",", ".")):
        try:
            value = float(candidate)
        except ValueError:
            continue
        if math.isfinite(value):  # a 400-digit "number" is no reading at all
            out.add(round(value, 4))
    if _GROUPED.fullmatch(token):  # 50,000 / 1.234.567: never a round decimal like 50.0
        whole = float(re.sub(r"[.,]", "", token))
        out = {v for v in out if v == whole or v != int(v)}
    return out


def allowed_numbers(data: Any) -> set[float]:
    allowed = set(FREE)

    def walk(obj: Any) -> None:
        if isinstance(obj, bool) or obj is None:
            return
        if isinstance(obj, (int, float)):
            allowed.update(_variants(float(obj)))
        elif isinstance(obj, str):
            for token in _IN_REPORT.findall(obj):  # "v8", "MOD13Q1" don't allow 8 or 13
                for value in _readings(token):
                    allowed.update(_variants(value))
        elif isinstance(obj, dict):
            for key, value in obj.items():
                walk(key)
                walk(value)
        elif isinstance(obj, (list, tuple)):
            for value in obj:
                walk(value)

    walk(data)
    return allowed


def unknown_numbers(text: str, allowed: set[float]) -> list[str]:
    return [t for t in _IN_REPORT.findall(text) if not (_readings(t) & allowed)]


def find_unknown(report: Any, allowed: set[float]) -> list[str]:
    found: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, str):
            found.extend(unknown_numbers(obj, allowed))
        elif isinstance(obj, dict):
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(report)
    return list(dict.fromkeys(found))


def scrub(report: Any, allowed: set[float]) -> tuple[Any, int]:
    """Drop list items and sentences that still contain unknown numbers. Returns (report, n)."""
    removed = 0

    def clean(obj: Any) -> Any:
        nonlocal removed
        if isinstance(obj, str):
            if not unknown_numbers(obj, allowed):
                return obj
            kept = [s for s in _SENTENCE.split(obj) if not unknown_numbers(s, allowed)]
            removed += 1
            return " ".join(kept)
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            out = []
            for item in obj:
                if isinstance(item, str) and unknown_numbers(item, allowed):
                    removed += 1
                    continue
                out.append(clean(item))
            return out
        return obj

    return clean(report), removed
