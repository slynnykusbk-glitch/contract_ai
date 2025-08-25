param([string]$BaseUrl = "https://127.0.0.1:9443")
Write-Host "Health:"
try {
  Invoke-WebRequest -UseBasicParsing "$BaseUrl/health" | Select-Object -Expand Content
} catch {
  Write-Host "health request failed" $_
}
Write-Host "Draft test:"
$payload = '{"text":"Clause for diagnostics"}'
try {
  Invoke-WebRequest -UseBasicParsing "$BaseUrl/api/gpt/draft?mock=true" -Method Post -Body $payload -ContentType "application/json" | Select-Object -Expand Content
} catch {
  Write-Host "draft request failed" $_
}
