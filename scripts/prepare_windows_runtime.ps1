param(
    [Parameter(Mandatory = $true)]
    [string]$PythonVersion,

    [string]$TargetDir = "",

    [switch]$Force
)

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "prepare_windows_runtime.ps1 must be run on Windows."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($TargetDir)) {
    $TargetDir = Join-Path $repoRoot "windows_runtime\python"
}

$embedUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("verse-listener-runtime-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "python-embed.zip"
$getPipPath = Join-Path $tempRoot "get-pip.py"

Write-Host "Preparing Windows helper runtime for VerseListener..."
Write-Host "Python version: $PythonVersion"
Write-Host "Target directory: $TargetDir"

New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    if ((Test-Path $TargetDir) -and -not $Force) {
        $pythonExe = Join-Path $TargetDir "python.exe"
        if (Test-Path $pythonExe) {
            Write-Host "Helper runtime already exists. Use -Force to rebuild it."
            exit 0
        }
    }

    if (Test-Path $TargetDir) {
        Remove-Item -Recurse -Force $TargetDir
    }
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

    Write-Host "Downloading embeddable Python from python.org..."
    Invoke-WebRequest -Uri $embedUrl -OutFile $zipPath

    Write-Host "Downloading get-pip bootstrap script..."
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath

    Write-Host "Expanding embeddable runtime..."
    Expand-Archive -LiteralPath $zipPath -DestinationPath $TargetDir -Force

    $pthFile = Get-ChildItem -LiteralPath $TargetDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pthFile) {
        throw "Could not locate python*._pth in $TargetDir"
    }

    $pthLines = Get-Content -LiteralPath $pthFile.FullName
    $updatedLines = New-Object System.Collections.Generic.List[string]
    $hasSitePackages = $false
    $hasImportSite = $false

    foreach ($line in $pthLines) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "#import site" -or $trimmed -eq "import site") {
            if (-not $hasImportSite) {
                $updatedLines.Add("import site")
                $hasImportSite = $true
            }
            continue
        }

        if ($trimmed -eq "Lib\site-packages") {
            $hasSitePackages = $true
        }

        $updatedLines.Add($line)
    }

    if (-not $hasSitePackages) {
        $updatedLines.Add("Lib\site-packages")
    }
    if (-not $hasImportSite) {
        $updatedLines.Add("import site")
    }

    Set-Content -LiteralPath $pthFile.FullName -Value $updatedLines -Encoding ASCII

    $sitePackagesDir = Join-Path $TargetDir "Lib\site-packages"
    New-Item -ItemType Directory -Force -Path $sitePackagesDir | Out-Null

    $pythonExe = Join-Path $TargetDir "python.exe"
    if (-not (Test-Path $pythonExe)) {
        throw "python.exe was not found after expanding the embeddable runtime."
    }

    Write-Host "Bootstrapping pip into the helper runtime..."
    & $pythonExe $getPipPath --no-warn-script-location

    Write-Host "Upgrading helper runtime packaging tools..."
    & $pythonExe -m pip install --upgrade pip setuptools wheel --disable-pip-version-check

    Write-Host "Verifying pip..."
    & $pythonExe -m pip --version

    Write-Host ""
    Write-Host "Helper runtime is ready."
    Write-Host "Builds can now bundle $TargetDir so in-app add-on installs work without Python on the target PC."
}
finally {
    Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue
}
