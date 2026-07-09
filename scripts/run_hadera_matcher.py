"""
Matcher runner for Hadera (Bartech, https://hadera.bartech-net.co.il).

Run from project root after hadera_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_hadera_matcher.py
"""

from transform.matcher import run

run(
    projects_path='docs/Hadera_Projects_08072026.xlsx',
    permits_path='outputs/hadera_fresh.csv',
    city_hebrew='חדרה',
    output_path='outputs/hadera_report.xlsx',
    matched_cache_path='outputs/hadera_matched_cache.json',
    permit_url_base='https://hadera.bartech-net.co.il/PermitApplicationDetails?Entity_Number=',
)
