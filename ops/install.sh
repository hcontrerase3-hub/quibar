#!/bin/bash
set -Eeuo pipefail
usage() { echo "Uso: sudo ops/install.sh /ruta/release [--kiosk] [--dry-run]"; }
[[ $# -ge 1 ]] || { usage; exit 1; }
source_dir="$(cd -- "$1" && pwd -P)"
shift
kiosk=0
dry_run=0
for arg in "$@"; do
  case "$arg" in --kiosk) kiosk=1 ;; --dry-run) dry_run=1 ;; *) usage; exit 1 ;; esac
done
[[ -f "$source_dir/backend/app.py" && -f "$source_dir/dist/index.html" ]] || { echo "El release debe incluir backend y dist (npm run build)" >&2; exit 1; }
[[ "$source_dir" != /opt/quibar ]] || { echo "Entrega el release desde otra carpeta para no sincronizar sobre sí mismo" >&2; exit 1; }
if [[ "$dry_run" == 1 ]]; then
  echo "Instalar código de $source_dir en /opt/quibar; datos en /var/lib/quibar; kiosco=$kiosk"
  exit 0
fi
[[ "$EUID" -eq 0 ]] || { echo "Ejecuta con sudo" >&2; exit 1; }
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo "Este instalador requiere Ubuntu 24.04 LTS" >&2; exit 1; }
for cmd in rsync python3 systemctl runuser; do command -v "$cmd" >/dev/null || { echo "Falta $cmd" >&2; exit 1; }; done
python3 -m venv --help >/dev/null || { echo "Instala python3-venv" >&2; exit 1; }
if [[ "$kiosk" == 1 ]]; then
  for cmd in openbox lightdm xset unclutter; do command -v "$cmd" >/dev/null || { echo "Falta $cmd (instala lightdm openbox x11-xserver-utils unclutter)" >&2; exit 1; }; done
  [[ -x /usr/lib/xorg/Xorg || -x /usr/bin/Xorg ]] || { echo "Instala xserver-xorg" >&2; exit 1; }
  if [[ -L /etc/systemd/system/display-manager.service ]] && [[ "$(readlink -f /etc/systemd/system/display-manager.service)" != */lightdm.service ]]; then
    echo "Selecciona LightDM como gestor de sesión antes de instalar el kiosco" >&2
    exit 1
  fi
  command -v chromium >/dev/null || command -v chromium-browser >/dev/null || { echo "Instala Chromium" >&2; exit 1; }
fi
getent passwd quibar >/dev/null || useradd --system --home-dir /var/lib/quibar --shell /usr/sbin/nologin quibar
install -d -o quibar -g quibar -m 700 /var/lib/quibar /var/lib/quibar/media
install -d -m 755 /opt/quibar
# Environment and persistent data live outside the release directory.
rsync -a --exclude=.git --exclude=.env --exclude='.env.*' --exclude=.venv --exclude=node_modules \
  --exclude=__pycache__ --exclude='*.sqlite3*' --exclude='*.mbtiles' --exclude=backend/media --exclude=.next \
  "$source_dir/" /opt/quibar/
python3 -m venv /opt/quibar/.venv
/opt/quibar/.venv/bin/python -m pip install -r /opt/quibar/backend/requirements.lock
if [[ ! -f /etc/quibar.env ]]; then
  install -o root -g quibar -m 640 /dev/null /etc/quibar.env
  cat > /etc/quibar.env <<'ENV'
QUIBAR_DB_PATH=/var/lib/quibar/quibar.sqlite3
QUIBAR_MEDIA_DIR=/var/lib/quibar/media
QUIBAR_TILES_PATH=/var/lib/quibar/map.mbtiles
QUIBAR_DIST_DIR=/opt/quibar/dist
OLLAMA_URL=http://127.0.0.1:11434
QUIBAR_MODEL=qwen3:14b-q4_K_M
QUIBAR_MODEL_TIMEOUT=6
QUIBAR_MODEL_KEEP_ALIVE=-1
QUIBAR_ADMIN_NETWORKS=127.0.0.0/8,::1/128,100.64.0.0/10
ENV
fi
install -m 755 /opt/quibar/ops/manage.sh /usr/local/bin/quibar-manage
for unit in quibar.service quibar-model.service quibar-prune.service quibar-prune.timer; do
  install -m 644 "/opt/quibar/ops/systemd/$unit" "/etc/systemd/system/$unit"
done
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
systemctl enable --now quibar.service quibar-prune.timer
if systemctl list-unit-files ollama.service --no-legend | grep -q ollama; then
  systemctl enable --now quibar-model.service || echo "La precarga no finalizó; revisa journalctl -u quibar-model"
fi
echo "Instalación preparada. Crea el primer administrador con sudo quibar-manage create-admin CORREO --name NOMBRE."
echo "El modo kiosco se inicia en el próximo arranque de la sesión gráfica."
