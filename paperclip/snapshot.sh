#!/bin/sh
# Creates a restricted recovery bundle on the server. Run on that server as root.
set -eu
cd /opt/narimato-paperclip
docker exec -u node narimato-paperclip node --import ./cli/node_modules/tsx/dist/loader.mjs cli/src/index.ts db:backup --json >/dev/null
umask 077
mkdir -p /root/paperclip-backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
bundle="/root/paperclip-backups/paperclip-recovery-$stamp.tar.gz"
factory_snapshot="/root/paperclip-backups/factory-$stamp.sqlite3"
if [ -f /var/lib/narimato-factory/factory.sqlite3 ]; then
  python3 /opt/narimato-factory/worker.py backup "$factory_snapshot"
  set -- opt/narimato-factory etc/systemd/system/narimato-factory.service "${factory_snapshot#/}"
else
  set --
fi
if [ -f /etc/paperclip-classscout.env ]; then
  set -- "$@" etc/paperclip-classscout.env
fi
if [ -f /etc/paperclip-brave.env ]; then
  set -- "$@" etc/paperclip-brave.env
fi
if [ -f /etc/paperclip-padel.env ]; then
  set -- "$@" etc/paperclip-padel.env
fi
if [ -f /etc/paperclip-slg.env ]; then
  set -- "$@" etc/paperclip-slg.env
fi
for helper in snapshot.sh backup.py scheduled-backup.py restore-drill.py configure-slg.py; do
  if [ -f "/opt/narimato-paperclip/$helper" ]; then
    set -- "$@" "opt/narimato-paperclip/$helper"
  fi
done
# SQL backups, persistent files, keys and deployment config; exclude live DB files.
tar --exclude=opt/narimato-paperclip/data/instances/default/db -czf "$bundle" -C / opt/narimato-paperclip/.env opt/narimato-paperclip/compose.yaml opt/narimato-paperclip/local-ai.json opt/narimato-paperclip/access opt/narimato-paperclip/data etc/paperclip-access.env etc/paperclip-local-ai.env etc/caddy/Caddyfile etc/systemd/system/paperclip-access.service "$@"
chmod 600 "$bundle"
printf '%s\n' "$bundle"
