#!/usr/bin/env bash
# Sauvegarde AMS — à lancer via cron sur le serveur.
#
# Prise en charge automatique :
#   - Postgres (DATABASE_URL=postgres://...)  -> pg_dump (format custom, restauration avec pg_restore)
#   - SQLite (DATABASE_URL=sqlite:///... ou absente) -> python manage.py dumpdata (JSON gzippé)
#   - média (media/)                           -> archive tar.gz (si le dossier existe)
#
# Rotation : seuls les KEEP (défaut 14) sauvegardes les plus récentes sont conservées.
#
# Utilisation :
#   ./deploy/backup.sh
#
# Variables (avec défauts) :
#   BACKUP_DIR  répertoire de destination   (défaut : <repo>/backups)
#   KEEP        nombre de sauvegardes à garder (défaut : 14)
#   DATABASE_URL URL de connexion Postgres (sinon SQLite local)
#
# Exemples cron (VPS Debian/Ubuntu, root ou utilisateur du projet) :
#   # Tous les jours à 03:00
#   0 3 * * * cd /opt/AMS/aeventbackend-main && /bin/bash deploy/backup.sh >> /var/log/ams_backup.log 2>&1
#   # Toutes les 6 heures
#   0 */6 * * * cd /opt/AMS/aeventbackend-main && /bin/bash deploy/backup.sh >> /var/log/ams_backup.log 2>&1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-${BASE_DIR}/backups}"
KEEP="${KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "${BACKUP_DIR}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

DB_URL="${DATABASE_URL:-}"
DB_SAVED=""
MEDIA_SAVED=""

# ── Base de données ─────────────────────────────────────────────────────────
if [[ "${DB_URL}" == postgres* ]]; then
  log "Backup Postgres : ${BACKUP_DIR}/db-${STAMP}.dump"
  pg_dump "${DB_URL}" --format=custom --no-owner --file="${BACKUP_DIR}/db-${STAMP}.dump"
  DB_SAVED="${BACKUP_DIR}/db-${STAMP}.dump"
elif [[ "${DB_URL}" == sqlite* ]] || [[ -z "${DB_URL}" ]] && [[ -f "${BASE_DIR}/db.sqlite3" ]]; then
  log "Backup SQLite (dumpdata) : ${BACKUP_DIR}/db-${STAMP}.json.gz"
  if ( cd "${BASE_DIR}" && python manage.py dumpdata --exclude contenttypes --exclude auth.permission \
        | gzip > "${BACKUP_DIR}/db-${STAMP}.json.gz" ); then
    DB_SAVED="${BACKUP_DIR}/db-${STAMP}.json.gz"
  fi
else
  log "Aucune base détectée (DATABASE_URL vide et pas de db.sqlite3) — backup DB ignoré."
fi

# ── Média ────────────────────────────────────────────────────────────────────
if [[ -d "${BASE_DIR}/media" ]] && [[ -n "$(ls -A "${BASE_DIR}/media" 2>/dev/null || true)" ]]; then
  log "Backup média : ${BACKUP_DIR}/media-${STAMP}.tar.gz"
  tar -czf "${BACKUP_DIR}/media-${STAMP}.tar.gz" -C "${BASE_DIR}" media
  MEDIA_SAVED="${BACKUP_DIR}/media-${STAMP}.tar.gz"
fi

# ── Rotation ─────────────────────────────────────────────────────────────────
for PREFIX in db- media-; do
  mapfile -t OLD < <(find "${BACKUP_DIR}" -maxdepth 1 -name "${PREFIX}*.gz" -o -maxdepth 1 -name "${PREFIX}*.dump" | sort -r | tail -n "+$((KEEP + 1))")
  for f in "${OLD[@]:-}"; do
    if [[ -n "${f}" ]]; then
      rm -f "${f}"
      log "Rotation : suppression de ${f}"
    fi
  done
done

log "Terminé :"
[[ -n "${DB_SAVED}" ]] && log "  DB   -> ${DB_SAVED} ($(du -h "${DB_SAVED}" | cut -f1))"
[[ -n "${MEDIA_SAVED}" ]] && log "  média-> ${MEDIA_SAVED} ($(du -h "${MEDIA_SAVED}" | cut -f1))"
