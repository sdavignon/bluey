param(
    [string]$ApkPath = (Join-Path $PSScriptRoot 'Bluey-Android-debug.apk'),
    [string]$DeviceSerial = ''
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $ApkPath -PathType Leaf)) {
    throw "Download Bluey-Android-debug.apk into this directory, or pass -ApkPath with its location."
}
$ApkPath = (Resolve-Path -LiteralPath $ApkPath).Path
$ToolsRoot = Join-Path $PSScriptRoot '.tools'
$Adb = Join-Path $ToolsRoot 'platform-tools\adb.exe'
if (!(Test-Path -LiteralPath $Adb)) {
    New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null
    $Archive = Join-Path $ToolsRoot 'platform-tools.zip'
    Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools_r37.0.1-win.zip' -OutFile $Archive
    # Google publishes this digest in its signed-over-TLS SDK repository metadata.
    $ExpectedHash = 'e03e78b1d80b396f1c3358e31251cb31740e1110'
    if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA1).Hash.ToLowerInvariant() -ne $ExpectedHash) {
        Remove-Item -LiteralPath $Archive
        throw 'Android platform-tools checksum verification failed; nothing was installed.'
    }
    Expand-Archive -LiteralPath $Archive -DestinationPath $ToolsRoot -Force
    Remove-Item -LiteralPath $Archive
}
Write-Host 'Enable USB debugging in the phone Developer options, connect it by USB, and unlock the phone.'
Write-Host 'Accept the USB debugging authorization prompt on the phone for this PC.'
& $Adb start-server
if ($LASTEXITCODE -ne 0) { throw 'ADB could not start.' }
$Listing = & $Adb devices
if ($LASTEXITCODE -ne 0) { throw 'ADB could not list devices.' }
$Listing | ForEach-Object { Write-Host $_ }
$Ready = @($Listing | Where-Object { $_ -match '^\S+\s+device$' } | ForEach-Object { ($_ -split '\s+')[0] })
if (!$DeviceSerial) {
    if ($Ready.Count -eq 0) { throw 'No authorized phone found. Check the USB cable, phone prompt, and manufacturer USB driver, then run again.' }
    if ($Ready.Count -ne 1) { throw 'Multiple devices found. Run again with -DeviceSerial followed by the intended phone serial.' }
    $DeviceSerial = $Ready[0]
}
if ($DeviceSerial -notin $Ready) { throw 'The selected phone is not authorized or connected.' }
& $Adb -s $DeviceSerial install -r $ApkPath
if ($LASTEXITCODE -ne 0) {
    throw 'APK installation failed. If Android reports a signing-key conflict, decide whether to remove the older app yourself. This script will not uninstall it or erase app data.'
}
& $Adb -s $DeviceSerial shell am start -n 'co.visionairy.bluey/.MainActivity'
if ($LASTEXITCODE -ne 0) { throw 'Installed, but Android could not launch Bluey.' }
Write-Host 'Bluey installed and launched. Start the Windows host, put PC and phone on the same Wi-Fi, then pair in Bluey.'
