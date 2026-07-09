"""
Matcher runner for מיצפה אפק (Bartech, www.vmm.co.il).
Covers: באר יעקב.

Run from project root after mitzpe_afek_fresh.csv exists:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_mitzpe_afek_matcher.py
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects_08072026.xlsx',
    permits_path='outputs/mitzpe_afek_fresh.csv',
    city_hebrew='באר יעקב',
    output_path='outputs/mitzpe_afek_report.xlsx',
    matched_cache_path='outputs/mitzpe_afek_matched_cache.json',
    permit_url_base='https://www.vmm.co.il/PermitApplicationDetails?Entity_Number=',
    city_filter=['באר יעקב'],
)
