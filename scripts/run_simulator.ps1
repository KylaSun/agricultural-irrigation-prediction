param(
  [int]$Records = 120,
  [double]$Interval = 1.0
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $projectRoot 'src'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pythonCommand = if (Test-Path $venvPython) { $venvPython } else { 'python' }
& $pythonCommand (Join-Path $projectRoot 'collector\serial_collector.py') --simulate --max-records $Records --interval $Interval
