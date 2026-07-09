"""
Matcher runner for הראל (Bartech, www.v-harel.co.il).
Covers: מבשרת ציון.

Run from project root after harel_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_harel_matcher.py
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects_08072026.xlsx',
    permits_path='outputs/harel_fresh.csv',
    city_hebrew='מבשרת ציון',
    output_path='outputs/harel_report.xlsx',
    matched_cache_path='outputs/harel_matched_cache.json',
    permit_url_base='https://www.v-harel.co.il/PermitApplicationDetails?Entity_Number=',
    city_filter=['מבשרת ציון'],
)
