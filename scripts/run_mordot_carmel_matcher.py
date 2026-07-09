"""
Matcher runner for מורדות כרמל (Complot, site_id=61).
Covers: טירת הכרמל, נשר.

Run from project root after mordot_carmel_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_mordot_carmel_matcher.py
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects_08072026.xlsx',
    permits_path='outputs/mordot_carmel_fresh.csv',
    city_hebrew='מורדות כרמל',
    output_path='outputs/mordot_carmel_report.xlsx',
    matched_cache_path='outputs/mordot_carmel_matched_cache.json',
    permit_url_base='https://mordotcarmel.org/iturbakashot/#request/',
    city_filter=['טירת הכרמל', 'נשר'],
)
