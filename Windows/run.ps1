$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11+ from python.org with Tcl/Tk and the Python launcher.' }
}
& .venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& .venv\Scripts\python.exe -m bluey.app
if ($LASTEXITCODE -ne 0) { throw 'Bluey exited with an error.' }
