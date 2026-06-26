"""
Gush-helka (block-lot) parsing and matching.

Projects DB format:  "7128-259 , 7128-264 , 7128-265"  (space-comma-space)
Scraped format:      "7123-96; 7123-101"                (semicolon)
Both use GUSH-HELKA hyphen within each pair.
"""

import re
from typing import Set, Tuple


def parse(value) -> Set[Tuple[str, str]]:
    """
    Parse any gush-helka string into a set of (gush, helka) string tuples.
    Returns empty set for null/unparseable values.
    """
    if not value or (isinstance(value, float)):
        return set()

    value = str(value).strip()
    parts = re.split(r'[,;]\s*', value)

    result = set()
    for part in parts:
        part = part.strip()
        m = re.match(r'^(\d+)-(\d+)$', part)
        if m:
            result.add((m.group(1), m.group(2)))

    return result


def match(val1, val2) -> bool:
    """True if the two gush-helka values share at least one (gush, helka) pair."""
    s1 = parse(val1)
    s2 = parse(val2)
    if not s1 or not s2:
        return False
    return bool(s1 & s2)
