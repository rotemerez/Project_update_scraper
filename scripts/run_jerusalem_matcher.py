"""
Matcher runner for ירושלים (custom API, ykpubdata.jerusalem.muni.il).

Run from project root after jerusalem_fresh.csv exists (see run_jerusalem.py):
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_jerusalem_matcher.py

NOTE: request_category is always empty for Jerusalem (the source API has no
separate category field distinct from request_type -- see
scrapers/jerusalem/api_scraper.py). EXCLUDED_REQUEST_CATEGORIES therefore
can't filter anything here; this is only safe because the רישוי בניה search
already appears to return finalized permit files (תיקי רישוי), not
preliminary/info-request stages like בקשה מקדמית -- unconfirmed against a
real example, flag to Rotem if a permit that should've been excluded shows
up in the report.
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects.xlsx',
    permits_path='outputs/jerusalem_fresh.csv',
    city_hebrew='ירושלים',
    output_path='outputs/jerusalem_report.xlsx',
    matched_cache_path='outputs/jerusalem_matched_cache.json',
    permit_url_base='https://ykpubdata.jerusalem.muni.il/#/Rishui/ProcessInfo?SystemCode=26400046&TikNum=',
    city_filter=['ירושלים'],
)
