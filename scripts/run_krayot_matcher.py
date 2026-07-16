"""
Matcher runner for קריות (Bartech, www.vkrayot.co.il).
Covers: קרית ביאליק, קרית מוצקין, קרית ים.

Run from project root after krayot_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_krayot_matcher.py
"""

from transform.matcher import run

run(
    projects_path='docs/krayot_projects_30062026.xlsx',
    permits_path='outputs/krayot_fresh.csv',
    city_hebrew='קריות',
    output_path='outputs/krayot_report.xlsx',
    matched_cache_path='outputs/krayot_matched_cache.json',
    permit_url_base='https://www.vkrayot.co.il/PermitApplicationDetails?Entity_Number=',
)
