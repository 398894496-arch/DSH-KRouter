# One line for anyone on Windows (PowerShell, as yourself, no admin):
#   irm https://raw.githubusercontent.com/398894496-arch/DSH-KRouter/main/scripts/bootstrap.ps1 | iex
# Fetches the latest release into %LOCALAPPDATA%\dsh-krouter\<tag>, checks its SHA-256 against the release's SHA256SUMS,
# and runs scripts\bootstrap.py from there. Set $env:KROUTER_TAG first to stay on one release.
# If Python is missing it installs it for the current user with winget. Run again to upgrade.
# Keep this file ASCII-only: Windows PowerShell 5.1 reads a BOM-less script in the ANSI code page.
$ErrorActionPreference = "Stop"
$Repo = "398894496-arch/DSH-KRouter"
$Home_ = Join-Path $env:LOCALAPPDATA "dsh-krouter"
$BootArgs = @($args)

function Find-Python {
    foreach ($name in @("python", "py", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { return $cmd.Source }
    }
    return $null
}

$Python = Find-Python
if (-not $Python) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Output "Installing Python 3.12 for this user (winget) ..."
        winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements | Out-Null
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
        $Python = Find-Python
    }
    if (-not $Python) {
        Write-Output "Python 3 is required: install it from https://www.python.org (tick 'Add python.exe to PATH'), then run this line again."
        exit 1
    }
}

$Tag = $env:KROUTER_TAG
if (-not $Tag) { $Tag = (Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest").tag_name }
$Dest = Join-Path $Home_ $Tag
if (-not (Test-Path (Join-Path $Dest "scripts\bootstrap.py"))) {
    New-Item -ItemType Directory -Force -Path $Home_ | Out-Null
    $Tmp = Join-Path $env:TEMP ("krouter-dl-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
    $Ver = $Tag.TrimStart("v")
    $Base = "https://github.com/$Repo/releases/download/$Tag"
    $Pkg = Join-Path $Tmp "pkg.tgz"
    $Sums = Join-Path $Tmp "SHA256SUMS"
    $haveAsset = $true
    try {
        Invoke-WebRequest "$Base/dsh-krouter-$Ver.tgz" -OutFile $Pkg -UseBasicParsing
        Invoke-WebRequest "$Base/SHA256SUMS" -OutFile $Sums -UseBasicParsing
    } catch { $haveAsset = $false }
    if ($haveAsset) {
        # The release package carries a checksum: a mismatch stops the install
        $want = (Get-Content $Sums | Where-Object { $_ -like "* dsh-krouter-$Ver.tgz" } | ForEach-Object { ($_ -split " ")[0] })
        $got = (Get-FileHash $Pkg -Algorithm SHA256).Hash.ToLower()
        if (-not $want -or $want.ToLower() -ne $got) {
            Write-Output "Checksum mismatch for dsh-krouter-$Ver.tgz; nothing installed."
            Remove-Item $Tmp -Recurse -Force
            exit 1
        }
        tar -xzf $Pkg -C $Tmp
        if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
        Move-Item (Join-Path $Tmp "package") $Dest
        Write-Output "sha256 verified: dsh-krouter-$Ver.tgz"
    } else {
        Write-Output "Note: $Tag has no checksummed package; using the source archive (unverified)."
        $Zip = Join-Path $Tmp "src.zip"
        Invoke-WebRequest "https://github.com/$Repo/archive/refs/tags/$Tag.zip" -OutFile $Zip -UseBasicParsing
        Expand-Archive $Zip -DestinationPath $Tmp -Force
        if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
        Move-Item (Get-ChildItem $Tmp -Directory | Where-Object { $_.Name -like "DSH-KRouter-*" } | Select-Object -First 1).FullName $Dest
    }
    Remove-Item $Tmp -Recurse -Force
}
Set-Content -Path (Join-Path $Home_ "current.txt") -Value $Dest -Encoding ASCII
Write-Output "DSH-KRouter $Tag -> $Dest"
$env:PYTHONUTF8 = "1"
# Python prints UTF-8; without this the 5.1 console decodes it in the ANSI code page and Chinese turns to garbage
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
& $Python (Join-Path $Dest "scripts\bootstrap.py") @BootArgs
exit $LASTEXITCODE
