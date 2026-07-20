"""
Matcher runner for אשקלון (Complot, site_id=95).

Run from project root after ashkelon_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_ashkelon_matcher.py

No permit_url_base -- not confirmed yet for this committee (config/committees.py
has it as None); add once a public portal URL pattern is confirmed.
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects.xlsx',
    permits_path='outputs/ashkelon_fresh.csv',
    city_hebrew='אשקלון',
    output_path='outputs/ashkelon_report.xlsx',
    matched_cache_path='outputs/ashkelon_matched_cache.json',
    city_filter=['אשקלון'],
)
