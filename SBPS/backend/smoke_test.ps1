param(
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [int]$UserId = 1,
    [string]$Pin = "1234",
    [double]$Amount = 5.0
)

$ErrorActionPreference = "Stop"

Write-Host "[1/5] GET /health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET
$health | ConvertTo-Json -Depth 4

Write-Host "[2/5] GET /users"
$users = Invoke-RestMethod -Uri "$BaseUrl/users" -Method GET
$users | ConvertTo-Json -Depth 4

Write-Host "[3/5] POST /verify_pin"
$pinPayload = @{ user_id = $UserId; pin = $Pin } | ConvertTo-Json
$pinResult = Invoke-RestMethod -Uri "$BaseUrl/verify_pin" -Method POST -ContentType "application/json" -Body $pinPayload
$pinResult | ConvertTo-Json -Depth 4

Write-Host "[4/5] POST /pay"
$payPayload = @{ user_id = $UserId; amount = $Amount } | ConvertTo-Json
$payResult = Invoke-RestMethod -Uri "$BaseUrl/pay" -Method POST -ContentType "application/json" -Body $payPayload
$payResult | ConvertTo-Json -Depth 4

Write-Host "[5/5] GET /transactions?limit=5"
$transactions = Invoke-RestMethod -Uri "$BaseUrl/transactions?limit=5" -Method GET
$transactions | ConvertTo-Json -Depth 6

Write-Host "Smoke test completed." -ForegroundColor Green
