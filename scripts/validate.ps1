# Run data-quality validation
Write-Host "Running validation..." -ForegroundColor Cyan
python -m src.main validate
exit $LASTEXITCODE
