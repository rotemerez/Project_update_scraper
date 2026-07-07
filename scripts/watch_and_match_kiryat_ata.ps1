$logPath   = 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_kiryat_ata_D.txt'
$matchLog  = 'c:\R_PROJECTS\Project_update_scraper\outputs\matcher_kiryat_ata_D_log.txt'
$runScript = 'c:\R_PROJECTS\Project_update_scraper\scripts\_run_matcher_kiryat_ata_D.py'
$python    = 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe'

# Write the matcher invocation script
@'
from transform.matcher import run
run(
    projects_path='docs/Kiryat_Ata_Projects_30062026.xlsx',
    permits_path='outputs/kiryat_ata_fresh.csv',
    city_hebrew=u'קרית אתא',
    output_path='outputs/kiryat_ata_report.xlsx',
    matched_cache_path='outputs/kiryat_ata_matched_cache.json',
)
'@ | Set-Content -Path $runScript -Encoding UTF8

function Log($msg) {
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$ts] $msg"
    Write-Output $line
    Add-Content -Path $matchLog -Value $line
}

Log "Watcher started -- waiting for scrape D to finish (3318 permits)"

$checkCount = 0
while ($true) {
    Start-Sleep -Seconds 30
    $checkCount++

    if (-not (Test-Path $logPath)) {
        Log "Log file not found yet..."
        continue
    }

    $tail = Get-Content $logPath -Tail 5

    $done = $false
    foreach ($line in $tail) {
        if ($line -match '\[3318/3318\]' -or $line -match 'Saved.*kiryat_ata' -or $line -match 'scrape complete') {
            $done = $true; break
        }
    }

    # Near-completion fallback
    if (-not $done) {
        $lastLine = $tail | Select-Object -Last 1
        if ($lastLine -match '\[(\d+)/3318\]' -and [int]$Matches[1] -ge 3315) {
            Log "Near end at $($Matches[1])/3318 -- treating as complete"
            $done = $true
        }
    }

    if ($done) {
        Log "Scrape D complete."
        $tail | ForEach-Object { Log "  $_" }
        Log "Running matcher..."

        $env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
        $env:PYTHONUTF8 = '1'
        & $python $runScript 2>&1 | ForEach-Object {
            Log $_
        }

        Log "Matcher done. Report: outputs/kiryat_ata_report.xlsx"
        Remove-Item $runScript -ErrorAction SilentlyContinue
        break
    }

    # Log progress every ~5 min (every 10 x 30s checks)
    if ($checkCount % 10 -eq 0) {
        $lastLine = ($tail | Select-Object -Last 1)
        if ($lastLine -match '\[(\d+)/3318\]') {
            Log "Progress: $($Matches[1])/3318 ($([math]::Round([int]$Matches[1]/3318*100,1))%)"
        }
    }
}
