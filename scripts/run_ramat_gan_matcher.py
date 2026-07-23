"""
Matcher runner for רמת גן (Complot, site_id=3).

Run from project root after ramat_gan_fresh.csv exists (see run_ramat_gan.py):
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_ramat_gan_matcher.py

permit_url_base NOT YET CONFIRMED: Ramat Gan's public Complot frontend is hosted at its own
municipal domain (https://handasa.ramat-gan.muni.il/) rather than a *.complot.co.il subdomain
like other cities in this codebase (dispatcher.py, C:\\R_PROJECTS\\local_committee_scrapers).
Assumed the same /newengine/Pages/request2.aspx#request/ path used by every other Complot city
here (e.g. Ashkelon), but a direct fetch returned HTTP 403 (the frontend blocks non-browser
requests, same as other Complot sites) so this could not be verified end-to-end. Flag to Rotem
to confirm a real link opens correctly in a browser before relying on it in the backoffice.
"""

from transform.matcher import run

run(
    projects_path='docs/all_projects.xlsx',
    permits_path='outputs/ramat_gan_fresh.csv',
    city_hebrew='רמת גן',
    output_path='outputs/ramat_gan_report.xlsx',
    matched_cache_path='outputs/ramat_gan_matched_cache.json',
    permit_url_base='https://handasa.ramat-gan.muni.il/newengine/Pages/request2.aspx#request/',
    city_filter=['רמת גן'],
)
