"""
Matcher runner for תל אביב יפו.

Run from project root after tel_aviv_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_tel_aviv_matcher.py

No permit_url_base -- detail pages require Azure B2C login, there's no
public URL to link to (see docs/tlv_permit_api_findings.md).
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects.xlsx',
    permits_path='outputs/tel_aviv_fresh.csv',
    city_hebrew='תל אביב יפו',
    output_path='outputs/tel_aviv_report.xlsx',
    matched_cache_path='outputs/tel_aviv_matched_cache.json',
    city_filter=['תל אביב יפו'],
)
