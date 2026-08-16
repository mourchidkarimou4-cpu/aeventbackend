# Sauvegarde AMS locale (Windows) — lancez via le Planificateur de tâches si besoin.
#
#   - Base SQLite  -> python manage.py dumpdata (JSON gzippé, restauration avec loaddata)
#   - Média        -> copie du dossier media\ (si présent)
#   - Rotation     -> seuls les $Keep (défaut 14) sauvegardes les plus récentes sont conservées
#
# Utilisation :
#   powershell -ExecutionPolicy Bypass -File deploy\backup.ps1

$ErrorActionPreference = 'Stop'

$BaseDir = Split-Path -Parent $PSScriptRoot
$BackupDir = Join-Path $BaseDir 'backups'
$Keep = 14
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

function Write-Log([string]$Msg) {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Msg"
}

# ── Base de données ─────────────────────────────────────────────────────────
$DbFile = Join-Path $BaseDir 'db.sqlite3'
if (Test-Path -LiteralPath $DbFile) {
    $JsonGz = Join-Path $BackupDir "db-$Stamp.json.gz"
    Write-Log "Backup SQLite (dumpdata) : $JsonGz"
    Push-Location $BaseDir
    try {
        python manage.py dumpdata --exclude contenttypes --exclude auth.permission |
            python -c "import sys, gzip; gzip.open(r'$JsonGz', 'wt', encoding='utf-8').write(sys.stdin.read())"
    } finally {
        Pop-Location
    }
} else {
    Write-Log 'db.sqlite3 introuvable — backup DB ignoré.'
}

# ── Média ────────────────────────────────────────────────────────────────────
$MediaDir = Join-Path $BaseDir 'media'
if (Test-Path -LiteralPath $MediaDir) {
    $MediaZip = Join-Path $BackupDir "media-$Stamp.zip"
    Write-Log "Backup média : $MediaZip"
    Compress-Archive -Path $MediaDir -DestinationPath $MediaZip -Force
}

# ── Rotation ─────────────────────────────────────────────────────────────────
Get-ChildItem -Path $BackupDir -File | Where-Object { $_.Name -match '^(db|media)-.*\.(json\.gz|zip)$' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $Keep |
    ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force
        Write-Log "Rotation : suppression de $($_.Name)"
    }

Write-Log 'Terminé.'
