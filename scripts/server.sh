#!/bin/sh
set -eu
identity=/Users/chappie/.ssh/hetzner_ai
host=root@2.31.100.246
case "${1:-status}" in
 status) command='hostname; uname -m; uptime; free -h; df -h /; docker ps; docker stats --no-stream; ufw status; systemctl is-active caddy' ;;
 logs) command='docker logs --tail 60 narimato-ollama; journalctl -u caddy -n 30 --no-pager' ;;
 restart) command='cd /opt/narimato-ai && docker compose restart ollama' ;;
 *) printf 'Usage: sh scripts/server.sh [status|logs|restart]\n' >&2; exit 2 ;;
esac
exec ssh -i "$identity" -o BatchMode=yes -o ConnectTimeout=15 "$host" "$command"
