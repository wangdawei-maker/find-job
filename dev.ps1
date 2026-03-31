param(
  [int]$BackendPort = 8000
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$logsDir = Join-Path $root "logs"
if (!(Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

Write-Host "Starting backend (FastAPI)..." -ForegroundColor Cyan
$backendVenvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"
$backendCmd = @"
cd `"$backendDir`";
if (Test-Path `"$backendVenvActivate`") {
  & `"$backendVenvActivate`";
} else {
  Write-Host "backend .venv 不存在：请先运行 backend 目录下的 venv+pip install" -ForegroundColor Yellow;
  exit 1;
}
uvicorn main:app --host 127.0.0.1 --reload --port $BackendPort
"@
$backendProc = Start-Process -FilePath "powershell" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-Command", $backendCmd
) -PassThru -RedirectStandardOutput (Join-Path $logsDir "backend.log") -RedirectStandardError (Join-Path $logsDir "backend.err.log")

Write-Host "Starting frontend (React)..." -ForegroundColor Cyan
$frontendCmd = @"
cd `"$frontendDir`";
if (!(Test-Path "node_modules")) { npm install };
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
"@
$frontendProc = Start-Process -FilePath "powershell" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-Command", $frontendCmd
) -PassThru -RedirectStandardOutput (Join-Path $logsDir "frontend.log") -RedirectStandardError (Join-Path $logsDir "frontend.err.log")

Write-Host ""
Write-Host "Backend:   http://127.0.0.1:$BackendPort" -ForegroundColor Green
Write-Host "Frontend:  (see Vite console output)" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow

# Give child processes a moment to fully start.
Start-Sleep -Seconds 1
$backendProc.Refresh()
$frontendProc.Refresh()

$runningIds = @()
if (-not $backendProc.HasExited) {
  $runningIds += $backendProc.Id
} else {
  Write-Host "Backend process exited early (exit code: $($backendProc.ExitCode))." -ForegroundColor Red
}

if (-not $frontendProc.HasExited) {
  $runningIds += $frontendProc.Id
} else {
  Write-Host "Frontend process exited early (exit code: $($frontendProc.ExitCode))." -ForegroundColor Red
}

if ($runningIds.Count -eq 0) {
  Write-Host "No running services. Please check backend/frontend startup logs." -ForegroundColor Red
  exit 1
}

# Keep this launcher alive while any service is alive.
try {
  while ($true) {
    $alive = @()
    foreach ($id in $runningIds) {
      if (Get-Process -Id $id -ErrorAction SilentlyContinue) {
        $alive += $id
      }
    }
    if ($alive.Count -eq 0) {
      break
    }
    Start-Sleep -Seconds 1
  }
} finally {
  # If either process exited early, print last lines to help debugging.
  $backendLog = Join-Path $logsDir "backend.log"
  $frontendLog = Join-Path $logsDir "frontend.log"
  if (Test-Path $backendLog -and $backendProc.HasExited) {
    Write-Host "---- backend log (last 30 lines) ----" -ForegroundColor Yellow
    Get-Content $backendLog -Tail 30
  }
  if (Test-Path $frontendLog -and $frontendProc.HasExited) {
    Write-Host "---- frontend log (last 30 lines) ----" -ForegroundColor Yellow
    Get-Content $frontendLog -Tail 30
  }
}
