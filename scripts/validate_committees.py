"""
Bulk endpoint validator for all active committees in config/committees.py.

Sends one lightweight probe request per committee and reports whether the
endpoint responds with permit data. Does NOT scrape — no detail pages fetched.

Complot probe : GetBakashotByNumber b=2024 (list page, one year only)
Bartech probe : SearchPermitApplicationResults TypeOfPermit=51 page=1

Output: prints a summary table and writes outputs/committee_validation.csv
"""

import sys
import time
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, 'c:\\R_PROJECTS\\Project_update_scraper')
from config.committees import COMMITTEES

COMPLOT_BASE = 'https://handasi.complot.co.il/magicscripts/mgrqispi.dll'
TIMEOUT = 20

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8',
}


def _count_table_rows(html: str) -> int:
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if not table:
        return 0
    # Complot uses <tbody><tr>; Bartech uses <tr> directly (no tbody).
    # Count all <tr> elements minus the header row.
    rows = table.find_all('tr')
    return max(0, len(rows) - 1)


def probe_complot(site_id: int) -> tuple:
    """Returns (row_count, error_str). error_str is '' on success."""
    params = {
        'appname': 'cixpa',
        'prgname': 'GetBakashotByNumber',
        'siteid': site_id,
        'grp': 0,
        't': 0,
        'b': 2024,
        'l': 'false',
        'arguments': 'siteId,grp,t,b,l',
    }
    try:
        r = requests.get(COMPLOT_BASE, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = 'utf-8'
        rows = _count_table_rows(r.text)
        return rows, ''
    except Exception as e:
        return 0, str(e)[:80]


def probe_bartech(base_url: str) -> tuple:
    """Returns (row_count, error_str). error_str is '' on success."""
    url = base_url.rstrip('/') + '/SearchPermitApplicationResults/'
    params = {
        'searchType': 'ByDetails',
        'TypeOfPermit': 51,
        'g-recaptcha-response': 'x',
        'page': 1,
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = 'utf-8'
        rows = _count_table_rows(r.text)
        return rows, ''
    except Exception as e:
        return 0, str(e)[:80]


def main():
    active = [c for c in COMMITTEES if not c['exclude']]
    print(f'Probing {len(active)} active committees...\n')

    results = []
    for c in active:
        name = c['committee_name']
        scraper = c['scraper']

        if scraper == 'complot':
            rows, err = probe_complot(c['site_id'])
        elif scraper == 'bartech':
            rows, err = probe_bartech(c['base_url'])
        else:
            results.append({'committee': name, 'scraper': scraper, 'status': 'SKIP', 'rows': 0, 'error': 'no scraper'})
            continue

        if err:
            status = 'FAIL'
        elif rows == 0:
            status = 'WARN'  # connected but no rows — wrong site_id or WAF block
        else:
            status = 'OK'

        results.append({
            'committee': name,
            'scraper': scraper,
            'status': status,
            'rows': rows,
            'error': err,
        })

        icon = '[OK]  ' if status == 'OK' else ('[WARN]' if status == 'WARN' else '[FAIL]')
        suffix = f'{rows} rows' if not err else f'ERROR: {err}'
        print(f'{icon} {name:<30} {scraper:<8} {suffix}')
        time.sleep(0.5)

    # Summary
    ok   = sum(1 for r in results if r['status'] == 'OK')
    warn = sum(1 for r in results if r['status'] == 'WARN')
    fail = sum(1 for r in results if r['status'] == 'FAIL')
    print(f'\n--- Summary ---')
    print(f'  OK   : {ok}')
    print(f'  WARN : {warn}  (connected, 0 rows — check site_id or WAF)')
    print(f'  FAIL : {fail}  (connection/HTTP error)')

    if warn or fail:
        print('\nProblematic committees:')
        for r in results:
            if r['status'] in ('WARN', 'FAIL'):
                print(f'  [{r["status"]}] {r["committee"]} — {r["error"] or "0 rows"}')

    # Write CSV
    import csv, os
    os.makedirs('outputs', exist_ok=True)
    with open('outputs/committee_validation.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['committee', 'scraper', 'status', 'rows', 'error'])
        writer.writeheader()
        writer.writerows(results)
    print('\n[OK] Written to outputs/committee_validation.csv')


if __name__ == '__main__':
    main()
