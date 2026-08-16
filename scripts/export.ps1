# Export data to Google Sheets
Write-Host "Exporting to Google Sheets..." -ForegroundColor Cyan
python -m src.main export
exit $LASTEXITCODE
