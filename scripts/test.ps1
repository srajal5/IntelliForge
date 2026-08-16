# Run automated tests
Write-Host "Running tests..." -ForegroundColor Cyan
python -m src.main test
exit $LASTEXITCODE
