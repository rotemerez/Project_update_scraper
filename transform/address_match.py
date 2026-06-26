"""
Address matching between project names and scraped full_address values.

Project name examples:  "תל חי 5-9 בת ים"   (street, range, city)
Scraped address:        "תל חי 7 בת ים"      (street, number, city)

Strategy:
  1. Strip city from both.
  2. Extract street name and number(s) from the remainder.
  3. Project numbers may be a range (5-9) -> expand to a set.
  4. Require exact street match + scraped number is in project number set.
"""

import re
from typing import Tuple, List


def _strip_city(text: str, city: str) -> str:
    if city:
        # Remove city at the end (common pattern), also handle comma before city
        text = re.sub(r',?\s*' + re.escape(city) + r'\s*$', '', text).strip()
    return text


def _parse_street_and_numbers(text: str) -> Tuple[str, List[int]]:
    """
    Split "שם רחוב 12" or "שם רחוב 5-9" into (street, [numbers]).
    The number / range is expected at the end of the string.
    Handles optional letter suffix: "5 א" -> treated as number 5.
    """
    text = text.strip(' ,')

    # Match trailing number/range, optionally followed by a Hebrew letter
    m = re.search(r'(\d+)(?:-(\d+))?\s*[א-ת]?\s*$', text)
    if not m:
        return (_normalize_street(text), [])

    street = text[:m.start()].strip()
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    numbers = list(range(start, end + 1))

    return (_normalize_street(street), numbers)


def _normalize_street(street: str) -> str:
    street = re.sub(r'["\',.()\[\]]', '', street)
    street = re.sub(r'\s+', ' ', street).strip()
    return street


def match(project_name: str, scraped_address: str, city: str) -> bool:
    """
    True if project_name and scraped_address refer to the same address.
    city is used to strip the city suffix from both strings.
    """
    if not project_name or not scraped_address:
        return False

    proj_text = _strip_city(str(project_name), city)
    scrape_text = _strip_city(str(scraped_address), city)

    proj_street, proj_nums = _parse_street_and_numbers(proj_text)
    scrape_street, scrape_nums = _parse_street_and_numbers(scrape_text)

    if not proj_street or not scrape_street:
        return False

    if proj_street != scrape_street:
        return False

    # Both streets match; require number confirmation on both sides.
    # If either side has no parseable number, reject — street-only is too imprecise.
    if not proj_nums or not scrape_nums:
        return False

    return any(n in proj_nums for n in scrape_nums)
