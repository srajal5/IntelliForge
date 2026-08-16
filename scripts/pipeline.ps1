# Run pipeline with safe development defaults
param(
    [int]$Limit = 10,
    [int]$Workers = 5
)
Write-Host "Running pipeline (limit=$Limit, workers=$Workers)..." -ForegroundColor Cyan
python -m src.main pipeline --limit $Limit --workers $Workers
exit $LASTEXITCODE
