# Instalación del tótem Quíbar en Ubuntu

El destino es Ubuntu 24.04 LTS con Docker/Compose, Nginx local, Chromium/Openbox y systemd. Python, Node y Ollama quedan dentro de contenedores; el servidor gráfico, navegador y controladores táctiles/gráficos se ejecutan en el anfitrión.

## Instalar el equipo dedicado

Transferir el repositorio completo, sin `.git/`, `.env`, `.quibar/`, `.venv/`, `node_modules/` ni datos generados. No hace falta compilar previamente `dist/`. El instalador prepara Docker desde paquetes Ubuntu si falta, habilita su servicio y construye la aplicación. Con `--kiosk` instala también los paquetes gráficos; confirmar LightDM y los controladores antes de la demostración.

```bash
ops/install.sh /ruta/repository --kiosk --dry-run
sudo ops/install.sh /ruta/repository --kiosk
sudo /opt/quibar/quibar admin
sudo /opt/quibar/quibar logs model-init
```

El código queda en `/opt/quibar`, la configuración privada en `/opt/quibar/.quibar/production.env` y los datos en volúmenes Docker. La unidad `quibar-compose.service` inicia los servicios al arrancar; sus políticas de reinicio los recuperan tras fallos. El instalador conserva configuración y datos existentes. El modelo se descarga en segundo plano sin bloquear catálogo, QR ni modo básico. La cuenta `quibar-kiosk` abre el navegador sin acceso administrativo a Docker. Mantener el puerto 8000 para el navegador del kiosco.

Para habilitar el mapa principal y recorridos del circuito, seguir [la preparación territorial](map-circuit.md): instalar MBTiles raster y extracción OSM PBF, configurar el origen del tótem y aprobar lugares con coordenadas verificadas. Valhalla y Piper se inician con el lanzador; sin esos datos la aplicación informa lo pendiente y mantiene la lista disponible.

No ejecutar el instalador en el equipo de desarrollo como sustituto de `./quibar desarrollar`. Los cambios de LightDM, políticas y systemd se aplican únicamente al mini PC. La configuración de encendido tras corte eléctrico se realiza en BIOS/UEFI.

### Migración de una instalación nativa

El instalador rechaza una API nativa activa. Antes de sustituirla, respaldar `/var/lib/quibar`, `/etc/quibar.env` y el release anterior. Detener y deshabilitar `quibar.service`, `quibar-model.service`, `quibar-prune.timer` y cualquier `quibar-prune.service` activo. Copiar el nuevo repositorio y ejecutar desde él `sudo ./quibar importar-datos /var/lib/quibar` **antes** del primer arranque Docker; los nombres de proyecto y volúmenes se conservarán al instalar en `/opt/quibar`. Seguir [la guía de importación](docker.md). No iniciar Docker con una semilla vacía antes de importar.

Los antiguos archivos se mantienen para recuperación; `ops/install-native.sh` conserva el instalador nativo anterior como alternativa explícita. No mezclar ambos servicios en el puerto 8000.

## Inferencia en el datacenter del cliente

Si el tótem no puede alojar el modelo, configurar `/opt/quibar/.quibar/production.env` con `QUIBAR_OLLAMA_MODE=remote`, `OLLAMA_URL` apuntando al servidor privado y `QUIBAR_MODEL` con un modelo instalado. Reiniciar con `sudo /opt/quibar/quibar iniciar`. Esta opción mantiene la IA habilitada y no arranca Ollama en el tótem ni solicita descargas al servidor. El datacenter puede alojar Qwen 3 u otro modelo compatible configurado por el cliente.

El anfitrión debe alcanzar ese servidor por Tailscale o la red privada del cliente; comprobar `quibar logs model-init`. Si la conexión falla, se entrega el catálogo mediante el modo básico y las siguientes consultas vuelven a intentar la IA. Validar latencia, capacidad y conectividad de la instalación final; la inferencia remota requiere esa red, aunque catálogo, mapas y QR sigan siendo locales.

## Supervisión y actualización

```bash
sudo systemctl status quibar-compose docker
sudo /opt/quibar/quibar logs
sudo /opt/quibar/quibar respaldo
sudo /opt/quibar/quibar admin reset-password operador@example.com
sudo /opt/quibar/quibar importar-mapa /var/tmp/territorio.mbtiles
```

Antes de actualizar, respaldar y detener con `quibar detener`. Ejecutar nuevamente el instalador desde el release nuevo y reiniciar `quibar-compose.service` si ya estaba activo. Las migraciones se ejecutan al iniciar la API. Los cambios de código no eliminan los volúmenes. Revertir migraciones exige el respaldo y su versión de código correspondiente.

El hardware de 16 GB/512 GB de la guía es un objetivo: validar RAM utilizable, temperatura y latencia del modelo de 14B en el equipo real. No se declara cumplimiento de respuesta inferior a cinco segundos sin esa medición.

## Cartografía local

Preparar un MBTiles raster de Quilaco y Santa Bárbara con atribución y licencia de uso local, y copiarlo a una ruta legible por el usuario `quibar`, como `/var/tmp/territorio.mbtiles`. Importarlo con `sudo /opt/quibar/quibar importar-mapa`; para una actualización usar `--replace`. El archivo se valida y cambia de forma atómica, sin reiniciar la API.

La aplicación no incluye un paquete cartográfico de terceros ni coordenadas o teléfonos ficticios añadidos a las fichas originales. Validar la cobertura de la zona y los niveles de zoom con fichas reales antes de la presentación. El endpoint `/api/quibar/map` informa si hay un paquete disponible. Los QR de ruta y de contacto se producen localmente y apuntan directamente al servicio correspondiente del teléfono.

## Administración remota por Tailscale

Instalar el cliente oficial en el mini PC e incorporarlo a la red privada autorizada. En las ACL de la tailnet, permitir acceso únicamente al grupo de administradores del proyecto. Publicar el servicio dentro de esa red con:

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8000
```

Abrir `https://NOMBRE-DEL-EQUIPO.TAILNET.ts.net/admin`. Tailscale termina HTTPS y la aplicación usa una cookie de sesión HttpOnly y Secure sobre ese origen. La sesión vence a las ocho horas; las operaciones de edición también requieren un token CSRF. La autenticación de aplicación se suma a la restricción de red y a las ACL. No se utiliza Tailscale Funnel ni se abre el puerto 8000 en la LAN o en el router.

La activación requiere una cuenta autorizada y DNS/certificados habilitados en esa tailnet. Ver [Tailscale Serve](https://tailscale.com/kb/1312/serve) para la configuración oficial. El instalador no incorpora el equipo a una cuenta ni configura ACL sin las credenciales del responsable.

## Respaldo y recuperación

Ejecutar `sudo /opt/quibar/quibar respaldo` y seguir [la recuperación e importación de datos](docker.md). El archivo incluye base, fotos y mapa, con API y limpieza pausadas; conservar también `.quibar/production.env` y la versión del código. No eliminar volúmenes al actualizar.

## Pruebas de campo requeridas

1. Reiniciar el mini PC y verificar inicio automático, pantalla completa, pantalla táctil y retorno al inicio tras 60 segundos.
2. Intentar salir mediante atajos, clic secundario, herramientas de desarrollo y cambio de terminal virtual. Revisar la aplicación efectiva de las políticas de Chromium en esa instalación.
3. Con Ollama funcionando, ejecutar preguntas conocidas, desconocidas y de seguimiento; registrar latencia y uso de memoria con Qwen 3.
4. Detener Ollama y confirmar que catálogo, filtros, mapa, QR y modo básico siguen disponibles. Reiniciar servicios y medir la recuperación.
5. Desconectar internet y comprobar teselas locales. Escanear ambos QR con un teléfono y distinguir generación local de navegación o mensajería del celular.
6. Aprobar y suspender una ficha desde un equipo autorizado en Tailscale; verificar el cambio en el catálogo y la denegación desde un equipo fuera de la tailnet.
7. Configurar en BIOS/UEFI el encendido tras retorno de energía y realizar una prueba controlada con respaldo previo. WAL mejora la recuperación, pero no garantiza inmunidad absoluta a fallas de hardware.
