param([string]$PythonExe = "python", [string]$ISCC = "")
$ErrorActionPreference = "Stop"
Push-Location -LiteralPath $PSScriptRoot
try {
    & $PythonExe -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    & $PythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
    & $PythonExe -m PyInstaller --noconfirm DesktopPetTemplate.spec
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
    if ($ISCC) {
        & $ISCC installer.iss
        if ($LASTEXITCODE -ne 0) { throw "Installer build failed" }
    }
    Get-ChildItem -LiteralPath dist -Filter *.exe -Recurse | Get-FileHash -Algorithm SHA256
} finally { Pop-Location }
