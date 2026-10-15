#!/bin/sh
# Nightly backup loop, run by the "backup" service in docker-compose.prod.yml.
# Writes a database dump and an audio archive to ./backups on the host and
# deletes copies older than BACKUP_KEEP_DAYS. Copy ./backups off the server
# regularly: a backup on the same disk does not survive losing the server.

KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
export PGPASSWORD="$POSTGRES_PASSWORD"

while true; do
  stamp=$(date -u +%Y%m%dT%H%M%SZ)

  # Write to .partial first so a half-written file is never mistaken for a backup.
  if pg_dump -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "/backups/db-$stamp.dump.partial"; then
    mv "/backups/db-$stamp.dump.partial" "/backups/db-$stamp.dump"
    echo "backup: db-$stamp.dump written"
  else
    rm -f "/backups/db-$stamp.dump.partial"
    echo "backup: DATABASE DUMP FAILED at $stamp" >&2
  fi

  if tar -C /data -czf "/backups/audio-$stamp.tar.gz.partial" audio; then
    mv "/backups/audio-$stamp.tar.gz.partial" "/backups/audio-$stamp.tar.gz"
    echo "backup: audio-$stamp.tar.gz written"
  else
    rm -f "/backups/audio-$stamp.tar.gz.partial"
    echo "backup: AUDIO ARCHIVE FAILED at $stamp" >&2
  fi

  find /backups \( -name 'db-*.dump' -o -name 'audio-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
  sleep 86400
done
