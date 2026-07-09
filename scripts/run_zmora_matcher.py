"""
Matcher runner for זמורה (Bartech, www.zmora.org.il).
Covers: מזכרת בתיה.

Run from project root after zmora_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_zmora_matcher.py
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects_08072026.xlsx',
    permits_path='outputs/zmora_fresh.csv',
    city_hebrew='מזכרת בתיה',
    output_path='outputs/zmora_report.xlsx',
    matched_cache_path='outputs/zmora_matched_cache.json',
    permit_url_base='https://www.zmora.org.il/PermitApplicationDetails?Entity_Number=',
    city_filter=['מזכרת בתיה'],
)
