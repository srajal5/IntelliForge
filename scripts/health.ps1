# Run health checks
Write-Host "Running health checks..." -ForegroundColor Cyan
python -m src.main health
exit $LASTEXITCODE
