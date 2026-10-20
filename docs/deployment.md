# Instalación del tótem Quíbar en Ubuntu

La instalación objetivo usa Ubuntu 24.04 LTS, FastAPI en `127.0.0.1:8000`, Chromium/Openbox y Ollama en `127.0.0.1:11434`. El equipo de desarrollo conserva su configuración; estos pasos se ejecutan en el mini PC destinado al tótem.

## Preparar un release e instalar

En el equipo de desarrollo, ejecutar `npm ci && npm test && npm run build`. Transferir el proyecto con `dist/`, omitiendo `.git/`, `.env`, `.venv/`, `node_modules/` y los datos generados. No se necesita Node en el mini PC si la compilación está incluida.

En Ubuntu instalar Python 3.12, `python3-venv`, `rsync`, `curl`, y Ollama desde su distribución oficial. Para el entorno gráfico se necesitan LightDM, Openbox, Chromium, `xserver-xorg`, `x11-xserver-utils` y `unclutter`. Seleccionar LightDM como gestor de sesión si existe otro. Confirmar que funcionan los controladores gráficos y táctiles antes de activar el kiosco.

```bash
# Revisión sin cambios del instalador
ops/install.sh /ruta/release --kiosk --dry-run
# Instalar en el equipo destino
sudo ops/install.sh /ruta/release --kiosk
ollama pull qwen3:14b-q4_K_M
sudo systemctl restart quibar-model.service
sudo quibar-manage create-admin operador@example.com --name 'Administrador local'
```

El instalador crea `quibar` como usuario del servicio y `quibar-kiosk` como usuario gráfico sin privilegios administrativos. Conserva `/etc/quibar.env` si ya existe. El código queda en `/opt/quibar`; base, fotografías y mapa residen en `/var/lib/quibar`. No copia una base de desarrollo ni crea credenciales de demostración. La configuración del kiosco se aplica en el siguiente inicio de la sesión gráfica.

El equipo de 16 GB/512 GB descrito en la guía es un objetivo de hardware; la memoria utilizable, la velocidad del modelo de 14B y la temperatura se deben comprobar en ese equipo. Si Ollama no está preparado, el catálogo y los QR siguen funcionando y el chat usa modo básico.

## Supervisión y mantenimiento

```bash
sudo systemctl status quibar quibar-model quibar-prune.timer
sudo journalctl -u quibar -u quibar-model --since today
curl -fsS http://127.0.0.1:8000/api/quibar/health
sudo quibar-manage migrate
sudo quibar-manage reset-password operador@example.com
sudo quibar-manage import-map /var/tmp/territorio.mbtiles
```

`quibar.service` reinicia la API tras fallos. `quibar-model.service` precarga el modelo cuando está instalado. El temporizador diario elimina métricas de más de 90 días y sesiones vencidas. Los servicios se ejecutan sin permisos para modificar el código; solo la API y la limpieza escriben en `/var/lib/quibar`.

El instalador de actualizaciones mantiene los datos y la configuración. Antes de actualizar, guardar un respaldo y detener la API mientras se reemplaza el release. Ejecutar otra vez el instalador, reiniciar `quibar.service` y comprobar la salud. Las migraciones iniciales preservan el catálogo anterior; la reversión completa se hace restaurando un respaldo previo y su versión de código.

## Cartografía local

Preparar un MBTiles raster de Quilaco y Santa Bárbara con atribución y licencia de uso local, y copiarlo a una ruta legible por el usuario `quibar`, como `/var/tmp/territorio.mbtiles`. Importarlo con `quibar-manage import-map`; para una actualización usar `--replace`. El archivo se valida y cambia de forma atómica, sin reiniciar la API.

La aplicación no incluye un paquete cartográfico de terceros ni coordenadas o teléfonos ficticios añadidos a las fichas originales. Validar la cobertura de la zona y los niveles de zoom con fichas reales antes de la presentación. El endpoint `/api/quibar/map` informa si hay un paquete disponible. Los QR de ruta y de contacto se producen localmente y apuntan directamente al servicio correspondiente del teléfono.

## Administración remota por Tailscale

Instalar el cliente oficial en el mini PC e incorporarlo a la red privada autorizada. En las ACL de la tailnet, permitir acceso únicamente al grupo de administradores del proyecto. Publicar el servicio dentro de esa red con:

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8000
```

Abrir `https://NOMBRE-DEL-EQUIPO.TAILNET.ts.net/admin`. Tailscale termina HTTPS y la aplicación usa una cookie de sesión HttpOnly y Secure sobre ese origen. La sesión vence a las ocho horas; las operaciones de edición también requieren un token CSRF. La autenticación de aplicación se suma a la restricción de red y a las ACL. No se utiliza Tailscale Funnel ni se abre el puerto 8000 en la LAN o en el router.

La activación requiere una cuenta autorizada y DNS/certificados habilitados en esa tailnet. Ver [Tailscale Serve](https://tailscale.com/kb/1312/serve) para la configuración oficial. El instalador no incorpora el equipo a una cuenta ni configura ACL sin las credenciales del responsable.

## Respaldo y recuperación

`quibar-manage backup /var/lib/quibar/backups/FECHA.sqlite3` usa la API de respaldo de SQLite, incluyendo transacciones confirmadas en WAL. Esa operación respalda la base; para una copia completa, incluir también `media/`, el mapa y `/etc/quibar.env`.

Para hacer una copia coherente de base y medios, detener `quibar.service`, `quibar-prune.timer` y cualquier ejecución de `quibar-prune.service`, realizar el respaldo y copiar los medios, y volver a iniciar el servicio y el temporizador. Conservar los archivos con acceso restringido: contienen usuarios, auditoría y antecedentes privados de comercios. Restaurar con los servicios detenidos y conservar propietario `quibar:quibar` y permisos de lectura/escritura solo para ese usuario.

## Pruebas de campo requeridas

1. Reiniciar el mini PC y verificar inicio automático, pantalla completa, pantalla táctil y retorno al inicio tras 60 segundos.
2. Intentar salir mediante atajos, clic secundario, herramientas de desarrollo y cambio de terminal virtual. Revisar la aplicación efectiva de las políticas de Chromium en esa instalación.
3. Con Ollama funcionando, ejecutar preguntas conocidas, desconocidas y de seguimiento; registrar latencia y uso de memoria con Qwen 3.
4. Detener Ollama y confirmar que catálogo, filtros, mapa, QR y modo básico siguen disponibles. Reiniciar servicios y medir la recuperación.
5. Desconectar internet y comprobar teselas locales. Escanear ambos QR con un teléfono y distinguir generación local de navegación o mensajería del celular.
6. Aprobar y suspender una ficha desde un equipo autorizado en Tailscale; verificar el cambio en el catálogo y la denegación desde un equipo fuera de la tailnet.
7. Configurar en BIOS/UEFI el encendido tras retorno de energía y realizar una prueba controlada con respaldo previo. WAL mejora la recuperación, pero no garantiza inmunidad absoluta a fallas de hardware.
