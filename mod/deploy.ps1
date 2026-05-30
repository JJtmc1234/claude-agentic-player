# Deploys claude-companion to the Factorio dedicated server's mods folder.
# Reads version from info.json and copies the source into a versioned folder
# at C:\FactorioServer\mods\<name>_<version>\.

$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "claude-companion"
$info = Get-Content -Path (Join-Path $src "info.json") -Raw | ConvertFrom-Json
$name = $info.name
$version = $info.version
$destBase = "C:\FactorioServer\mods"
$folderName = "{0}_{1}" -f $name, $version
$destFolder = Join-Path $destBase $folderName
$destZip = Join-Path $destBase ("{0}.zip" -f $folderName)

if (-not (Test-Path $destBase)) {
  New-Item -ItemType Directory -Path $destBase -Force | Out-Null
}

# Wipe ALL prior versions of this mod from the server folder. Factorio would
# load the highest version anyway; this just keeps things tidy.
Get-ChildItem -Path $destBase -Filter ("{0}_*.zip" -f $name) -ErrorAction SilentlyContinue |
  Remove-Item -Force
Get-ChildItem -Path $destBase -Filter ("{0}_*" -f $name) -Directory -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force

# Stage the source under a versioned folder name in a temp location so the
# zip's top-level directory matches what Factorio expects, then archive it
# with a python helper. PowerShell's Compress-Archive writes Windows-style
# backslashes inside the zip which the Factorio mod portal rejects.
$staging = Join-Path $env:TEMP ("claude-companion-deploy-{0}" -f ([guid]::NewGuid()))
New-Item -ItemType Directory -Path $staging | Out-Null
try {
  $stagedFolder = Join-Path $staging $folderName
  Copy-Item -Recurse -Path $src -Destination $stagedFolder
  $buildZipPy = Join-Path $PSScriptRoot "_build_zip.py"
  python $buildZipPy $stagedFolder $destZip
  if ($LASTEXITCODE -ne 0) { throw "build_zip.py failed (exit $LASTEXITCODE)" }
}
finally {
  Remove-Item -Recurse -Force $staging
}

# Also drop a copy into the repo's mod/dist folder so it syncs via OneDrive
# (or whatever the project root's sync mechanism is) to your other PCs.
# The repo .gitignore already excludes *.zip so this never gets committed.
$distDir = Join-Path $PSScriptRoot "dist"
if (-not (Test-Path $distDir)) {
  New-Item -ItemType Directory -Path $distDir | Out-Null
}
# Remove any older builds of this mod from dist so only the latest sits there.
Get-ChildItem -Path $distDir -Filter ("{0}_*.zip" -f $name) -ErrorAction SilentlyContinue |
  Remove-Item -Force
$distZip = Join-Path $distDir ("{0}.zip" -f $folderName)
Copy-Item -Path $destZip -Destination $distZip -Force

Write-Output ("deployed {0} v{1}" -f $name, $version)
Write-Output ("  server: {0}" -f $destZip)
Write-Output ("  dist:   {0}" -f $distZip)
