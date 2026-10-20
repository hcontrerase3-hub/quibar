#!/bin/bash
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Usa sudo quibar-manage ..." >&2; exit 1; }
[[ -f /etc/quibar.env ]] || { echo "Falta /etc/quibar.env" >&2; exit 1; }
set -a
source /etc/quibar.env
set +a
cd /opt/quibar
exec runuser --preserve-environment -u quibar -- /opt/quibar/.venv/bin/python -m backend.cli "$@"
