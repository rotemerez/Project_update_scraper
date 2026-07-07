from transform.matcher import run
run(
    projects_path='docs/Kiryat_Ata_Projects_30062026.xlsx',
    permits_path='outputs/kiryat_ata_fresh.csv',
    city_hebrew=u'קרית אתא',
    output_path='outputs/kiryat_ata_report.xlsx',
    matched_cache_path='outputs/kiryat_ata_matched_cache.json',
)
