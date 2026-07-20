"""
Matcher runner for תל אביב יפו against the GIS-layer scrape.

Run from project root after tel_aviv_gis_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_tel_aviv_gis_matcher.py

No permit_url_base -- the GIS layer has no public single-permit detail page.
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects.xlsx',
    permits_path='outputs/tel_aviv_gis_fresh.csv',
    city_hebrew='תל אביב יפו',
    output_path='outputs/tel_aviv_gis_report.xlsx',
    matched_cache_path='outputs/tel_aviv_gis_matched_cache.json',
    city_filter=['תל אביב יפו'],
)
