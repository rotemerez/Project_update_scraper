"""
Matcher runner for ישובי הברון (Complot, site_id=14).
Covers: זכרון יעקב, אור עקיבא, בנימינה גבעת עדה, ג'סר א-זרקא.

Run from project root after yishuvei_habaron_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_yishuvei_habaron_matcher.py
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects_08072026.xlsx',
    permits_path='outputs/yishuvei_habaron_fresh.csv',
    city_hebrew='ישובי הברון',
    output_path='outputs/yishuvei_habaron_report.xlsx',
    matched_cache_path='outputs/yishuvei_habaron_matched_cache.json',
    city_filter=['זכרון יעקב', 'אור עקיבא', 'בנימינה גבעת עדה', "ג'סר א זרקא"],
)
