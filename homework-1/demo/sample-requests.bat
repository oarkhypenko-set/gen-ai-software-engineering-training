@echo off
rem Run sample requests against a running API and print each status code and body.
rem Windows version of sample-requests.sh (uses curl.exe, built into Windows 10+).
rem
rem   demo\sample-requests.bat                  all requests, then the rate-limit demo
rem   demo\sample-requests.bat --no-rate-limit  skip the rate-limit demo
rem   set BASE_URL=http://localhost:5000 ^& demo\sample-requests.bat
rem
rem Start the server first (demo\run.bat). Best run against fresh demo data.
setlocal EnableDelayedExpansion

if not defined BASE_URL set "BASE_URL=http://localhost:3000"

where curl.exe >nul 2>&1 || (
    echo curl.exe was not found. It ships with Windows 10 1803+; otherwise install it from https://curl.se 1>&2
    exit /b 1
)
curl.exe -s -o nul "%BASE_URL%/transactions" || (
    echo API is not reachable at %BASE_URL%. Start it with demo\run.bat first. 1>&2
    exit /b 1
)

rem JSON bodies: quotes are written as \" so curl.exe receives them unchanged.

echo ##### Task 1: core endpoints
set "BODY={\"toAccount\": \"ACC-12345\", \"amount\": 500, \"currency\": \"USD\", \"type\": \"deposit\"}"
call :post "Create a deposit (201)"
set "BODY={\"fromAccount\": \"ACC-12345\", \"toAccount\": \"ACC-67890\", \"amount\": 100.50, \"currency\": \"USD\", \"type\": \"transfer\"}"
call :post "Create a transfer (201)"
set "BODY={\"fromAccount\": \"ACC-12345\", \"amount\": 1000000, \"currency\": \"USD\", \"type\": \"withdrawal\"}"
call :post "Withdrawal larger than the balance (201, status failed)"
call :get "List all transactions (200)" "/transactions"
call :get "Get transaction by id (200)" "/transactions/tx-0003"
call :get "Unknown transaction id (404)" "/transactions/does-not-exist"
call :get "Account balance (200)" "/accounts/ACC-12345/balance"

echo.
echo ##### Task 2: validation
set "BODY={\"fromAccount\": \"ACC-12345\", \"toAccount\": \"ACC-67890\", \"amount\": -5, \"currency\": \"XYZ\", \"type\": \"transfer\"}"
call :post "Negative amount and invalid currency (400)"
set "BODY={\"fromAccount\": \"12345\", \"toAccount\": \"ACC-678\", \"amount\": 10.555, \"currency\": \"USD\", \"type\": \"refund\"}"
call :post "3 decimals, bad accounts, unknown type (400)"

echo.
echo ##### Task 3: filtering
call :get "By account (200)" "/transactions?accountId=ACC-67890"
call :get "By type (200)" "/transactions?type=transfer"
call :get "By date range (200)" "/transactions?from=2024-01-01&to=2024-01-10"
call :get "Combined (200)" "/transactions?accountId=ACC-12345&type=deposit&from=2024-01-01&to=2024-12-31"
call :get "Invalid filters (400)" "/transactions?accountId=bad&from=yesterday"

echo.
echo ##### Task 4: additional features
call :get "A. Account summary (200)" "/accounts/ACC-12345/summary"
call :get "B. Interest rate=0.05 for 30 days (200)" "/accounts/ACC-12345/interest?rate=0.05&days=30"
call :get "B. Invalid interest parameters (400)" "/accounts/ACC-12345/interest?rate=5&days=0"
call :get "C. CSV export (200)" "/transactions/export?format=csv&accountId=ACC-ABC12"
call :get "C. Unsupported format (400)" "/transactions/export?format=xml"

if /i "%~1"=="--no-rate-limit" goto :end

echo.
echo ##### D. Rate limiting: sending requests until the API answers 429
set /a N=0
:rate_loop
set /a N+=1
if %N% gtr 110 (
    echo No 429 received after 110 requests.
    goto :end
)
set "CODE="
for /f %%c in ('curl.exe -s -o nul -w "%%{http_code}" "%BASE_URL%/transactions?type=deposit"') do set "CODE=%%c"
if not "%CODE%"=="429" goto :rate_loop
echo Request #%N% in this burst was rejected:
curl.exe -s -i "%BASE_URL%/transactions" | findstr /i /r /c:"^HTTP" /c:"^retry-after" /c:"^x-ratelimit" /c:"error"

:end
endlocal
exit /b 0


rem --- Subroutines -----------------------------------------------------------

rem call :get "Title" "/path?query"
:get
echo.
echo === %~1
echo $ curl "%BASE_URL%%~2"
curl.exe -s -w "\n--> HTTP %%{http_code}\n" "%BASE_URL%%~2"
exit /b 0

rem call :post "Title"   (JSON body in the BODY variable)
:post
echo.
echo === %~1
echo $ curl -X POST "%BASE_URL%/transactions" -H "Content-Type: application/json" -d "!BODY!"
curl.exe -s -w "\n--> HTTP %%{http_code}\n" -X POST "%BASE_URL%/transactions" -H "Content-Type: application/json" -d "!BODY!"
exit /b 0
