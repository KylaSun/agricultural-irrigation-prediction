$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $projectRoot 'src'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pythonCommand = if (Test-Path $venvPython) { $venvPython } else { 'python' }
& $pythonCommand -m streamlit run (Join-Path $projectRoot 'app\streamlit_app.py')
