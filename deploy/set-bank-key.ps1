# Bankabruf auf dem Server einrichten: Application-ID und privaten Schlüssel von Enable Banking
# in /opt/fintrack/.env eintragen und FinTrack neu starten. Ein vorhandener Eintrag wird ersetzt
# (auch für einen neuen Schlüssel später). Der Schlüssel geht direkt per SSH auf den Server und
# wird nirgends angezeigt.
#
# Aufruf (ohne Angaben: neueste .pem-Datei im Download-Ordner):
#   powershell -ExecutionPolicy Bypass -File deploy\set-bank-key.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\set-bank-key.ps1 -KeyFile "C:\Pfad\zur\datei.pem"
param(
    [string]$AppId = 'adf5f142-2f04-46f8-949f-7a4b1fb5f478',
    [string]$KeyFile = '',
    [string]$Server = 'root@69.62.121.122'
)
$ErrorActionPreference = 'Stop'

if (-not $KeyFile) {
    $downloads = Join-Path $env:USERPROFILE 'Downloads'
    $found = Get-ChildItem -Path $downloads -Filter '*.pem' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $found) { throw "Keine .pem-Datei in $downloads gefunden. Bitte mit -KeyFile den Pfad angeben." }
    $KeyFile = $found.FullName
}
if (-not (Test-Path $KeyFile)) { throw "Datei nicht gefunden: $KeyFile" }

$lines = Get-Content -Path $KeyFile | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if (-not ($lines[0] -like '-----BEGIN*PRIVATE KEY-----')) { throw "$KeyFile ist kein privater Schlüssel (PEM)." }
$oneLine = ($lines -join '\n') + '\n'

Write-Host "Schlüssel:  $KeyFile"
Write-Host "App-ID:     $AppId"
Write-Host "Server:     $Server"
$answer = Read-Host 'Eintragen und FinTrack neu starten? (j/n)'
if ($answer -ne 'j') { Write-Host 'Abgebrochen, nichts geändert.'; exit 1 }

# Der Schlüssel kommt über die Standardeingabe, nicht in der Befehlszeile (dort wäre er für andere Prozesse sichtbar)
$remote = @"
set -e
f=/opt/fintrack/.env
IFS= read -r key
cp "`$f" "`$f.bak-bank"
sed -i '/^ENABLE_BANKING_/d' "`$f"
printf 'ENABLE_BANKING_APP_ID=%s\nENABLE_BANKING_PRIVATE_KEY=%s\n' '$AppId' "`$key" >> "`$f"
chmod 600 "`$f" "`$f.bak-bank"
echo 'Eingetragen. Starte FinTrack neu ...'
sh /opt/fintrack/src/deploy/server-deploy.sh
"@ -replace "`r", ''

$oneLine | ssh $Server $remote
if ($LASTEXITCODE -ne 0) { throw "Auf dem Server ist etwas schiefgegangen (Exit-Code $LASTEXITCODE)." }
Write-Host ''
Write-Host 'Fertig. In FinTrack: Einstellungen -> Bankabruf -> Bei der Bank anmelden.'
