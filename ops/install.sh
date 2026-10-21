#!/bin/bash
set -Eeuo pipefail
usage() { echo "Uso: sudo ops/install.sh /ruta/repository [--kiosk] [--dry-run]"; }
[[ $# -ge 1 ]] || { usage; exit 1; }
source_dir="$(cd -- "$1" && pwd -P)"
shift
kiosk=0
dry_run=0
for arg in "$@"; do
  case "$arg" in --kiosk) kiosk=1 ;; --dry-run) dry_run=1 ;; *) usage; exit 1 ;; esac
done
[[ -f "$source_dir/Dockerfile" && -f "$source_dir/quibar" ]] || { echo "Falta el repositorio completo" >&2; exit 1; }
[[ "$source_dir" != /opt/quibar ]] || { echo "Entrega el release desde otra carpeta" >&2; exit 1; }
if [[ "$dry_run" == 1 ]]; then
  echo "Instalar Docker/Compose y código en /opt/quibar; datos en volúmenes Docker; kiosco=$kiosk"
  exit 0
fi
[[ "$EUID" -eq 0 ]] || { echo "Ejecuta con sudo" >&2; exit 1; }
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo "Requiere Ubuntu 24.04 LTS" >&2; exit 1; }
if systemctl is-active --quiet quibar.service || systemctl is-enabled --quiet quibar.service 2>/dev/null; then
  echo "Detén y respalda la instalación nativa antes de migrar; consulta docs/deployment.md" >&2
  exit 1
fi
apt-get update
apt-get install -y rsync curl
if ! command -v docker >/dev/null; then apt-get install -y docker.io docker-compose-v2; fi
docker compose version >/dev/null || { echo "Instala el plugin Docker Compose v2" >&2; exit 1; }
systemctl enable --now docker.service
if [[ "$kiosk" == 1 ]]; then
  apt-get install -y lightdm openbox chromium-browser xserver-xorg x11-xserver-utils unclutter
  if [[ -L /etc/systemd/system/display-manager.service ]] && [[ "$(readlink -f /etc/systemd/system/display-manager.service)" != */lightdm.service ]]; then
    echo "Selecciona LightDM como gestor de sesión antes de instalar el kiosco" >&2
    exit 1
  fi
fi
install -d -m 755 /opt/quibar
rsync -a --exclude=.git --exclude=.quibar --exclude=.env --exclude='.env.*' --exclude=.venv --exclude=node_modules \
  --exclude=__pycache__ --exclude='*.sqlite3*' --exclude='*.mbtiles' --exclude='*.osm.pbf' --exclude=data/routing --exclude=.impeccable/review --exclude=backend/media --exclude=backups \
  "$source_dir/" /opt/quibar/
install -d -m 700 /opt/quibar/.quibar
if [[ ! -f /opt/quibar/.quibar/production.env ]]; then
  install -m 600 /opt/quibar/docker.env.example /opt/quibar/.quibar/production.env
fi
install -m 644 /opt/quibar/ops/systemd/quibar-compose.service /etc/systemd/system/quibar-compose.service
if [[ "$kiosk" == 1 ]]; then
  getent passwd quibar-kiosk >/dev/null || useradd --create-home --shell /bin/bash quibar-kiosk
  install -d -m 755 /home/quibar-kiosk/.config/openbox /etc/lightdm/lightdm.conf.d /etc/X11/xorg.conf.d /etc/systemd/user
  install -m 755 /opt/quibar/ops/kiosk/autostart /home/quibar-kiosk/.config/openbox/autostart
  install -m 644 /opt/quibar/ops/kiosk/rc.xml /home/quibar-kiosk/.config/openbox/rc.xml
  install -m 644 /opt/quibar/ops/kiosk/lightdm.conf /etc/lightdm/lightdm.conf.d/50-quibar.conf
  install -m 644 /opt/quibar/ops/kiosk/xorg.conf /etc/X11/xorg.conf.d/10-quibar.conf
  install -m 644 /opt/quibar/ops/systemd/quibar-browser.service /etc/systemd/user/quibar-browser.service
  for policy_dir in /etc/chromium/policies/managed /var/snap/chromium/current/policies/managed; do
    install -d -m 755 "$policy_dir"
    install -m 644 /opt/quibar/ops/kiosk/chromium-policy.json "$policy_dir/quibar.json"
  done
  systemctl mask ctrl-alt-del.target
  systemctl enable lightdm.service
fi
systemctl daemon-reload
systemctl enable quibar-compose.service
systemctl restart quibar-compose.service
echo "Crea el administrador: sudo /opt/quibar/quibar admin"
echo "Revisa la descarga: sudo /opt/quibar/quibar logs model-init"
echo "El kiosco gráfico se inicia en el próximo inicio de sesión."
