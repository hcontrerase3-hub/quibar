# Docker: desarrollo, operación y migración

## Requisitos y arranque

Docker Desktop (contenedores Linux) en macOS/Windows, o Docker Engine y Compose v2 en Linux. Se requiere conexión la primera vez para imágenes, dependencias y modelo. Después, catálogo, mapas instalados e inferencia funcionan localmente. No se necesita Node, Python ni Ollama en el anfitrión.

`./quibar iniciar` construye la SPA y la imagen Python 3.12, aplica Alembic, espera la salud de API/Nginx y arranca la descarga/precarga del modelo en segundo plano. La descarga puede fallar sin detener el modo básico. `./quibar admin` crea el primer administrador de forma interactiva si falta. En Windows sustituir `./quibar` por `quibar.cmd`.

La configuración está en `.quibar/production.env` (plantilla: `docker.env.example`). Nunca se ejecuta como código ni reemplaza `.env`. Tras cambiarla, ejecutar de nuevo `iniciar`. Los contenedores reinician con Docker; Docker Desktop debe estar iniciado en el equipo.

## Servicios y límites de acceso

- `app`: FastAPI no privilegiado (UID 10001), SQLite WAL, fotos y mapa en `state`.
- `nginx`: publica únicamente `127.0.0.1:8000`; conecta por un socket Unix compartido. La API no tiene puerto TCP, incluso en modo nativo Linux.
- `ollama`: imagen oficial por CPU, sin puerto publicado, modelos en `models`.
- `model-init`: descarga el modelo configurado y lo precarga; consultar `logs model-init`.
- `maintenance`: elimina diariamente sesiones vencidas y métricas de más de 90 días.

Nginx reemplaza el origen de red reenviado por loopback, y conserva Host y HTTPS de Tailscale Serve. La restricción administrativa descansa en la publicación exclusiva en loopback, el socket privado y las ACL de Tailscale, además de contraseña y CSRF. La auditoría registra el proxy local, no atribuye la IP del visitante remoto. No publicar Nginx/Vite en `0.0.0.0`, montar el socket en otros servicios ni exponer Docker. Los encabezados de direcciones aportados por clientes se descartan. La cookie es Secure cuando el origen reenviado es HTTPS.

## Desarrollo

`./quibar desarrollar` usa el proyecto `quibar-dev`, con volúmenes independientes de `quibar`, API en 8001 y Vite en 3000. El código Python se monta en modo lectura con recarga de Uvicorn; Vite monta las fuentes y usa polling para Docker Desktop. `node_modules` permanece en un volumen Linux, separado del anfitrión. Un cambio de dependencias requiere volver a ejecutar `desarrollar`.

Las demás acciones usan `--dev`: `./quibar --dev logs`, `./quibar --dev admin`, `./quibar --dev detener`. El frontend de desarrollo y la API usan el mismo origen gracias al proxy de Vite.

## Ollama nativo opcional

Cambiar `QUIBAR_OLLAMA_MODE=native` y ejecutar `iniciar`. macOS/Windows usan `host.docker.internal`; Linux aplica `compose.native-linux.yaml`, dando red de anfitrión exclusivamente al cliente API y al inicializador para alcanzar `127.0.0.1:11434`. El servidor API sigue usando el socket Unix. No es necesario publicar Ollama en todas las interfaces.

Revisar `logs model-init` para confirmar conectividad y carga. Si Docker Desktop no alcanza el servicio nativo en ese sistema, volver al modo Docker predeterminado o usar un servidor privado remoto. Al cambiar desde Docker a nativo, ejecutar primero `detener` para liberar la memoria del contenedor Ollama anterior. GPU no está habilitada por defecto; depende de los controladores y hardware. Qwen 3 de 14B requiere validar RAM y latencia reales.

## Inferencia remota en producción o en el datacenter del cliente

Configurar el archivo del entorno elegido, por ejemplo:

```dotenv
QUIBAR_OLLAMA_MODE=remote
OLLAMA_URL=http://100.X.Y.Z:11434
QUIBAR_MODEL=gemma4:e2b
QUIBAR_MODEL_KEEP_ALIVE=5m
```

El anfitrión debe estar conectado a Tailscale y tener acceso al puerto 11434 mediante las ACL de esa red. Ejecutar `iniciar` y consultar `logs model-init`: comprueba conectividad y precarga el modelo existente, sin solicitar descargas ni arrancar un Ollama local. Si se cambia desde el modo Docker, ejecutar antes `detener`. No publicar el servidor en internet.

El modo remoto es una opción de producción cuando el tótem no puede alojar el modelo. Se configura la URL del servidor del cliente y el modelo que tenga instalado; Qwen 3 de 14B puede ejecutarse en ese servidor, sin necesitar memoria para el modelo en el tótem. La configuración actual reutiliza `gemma4:e2b`. En modo remoto la IA depende de la red privada y del servidor: si no responden, se conserva la atención básica. Este modo no demuestra inferencia sin red en el mini PC.

## Importar la instalación anterior

1. Detener la API nativa, su limpieza y cualquier proceso que escriba fotografías o mapas. Conservar la instalación y sus archivos originales.
2. Identificar la carpeta de datos: `backend/` del repositorio antiguo o `/var/lib/quibar` de la instalación nativa. Debe contener `quibar.sqlite3`, opcionalmente `media/` y `map.mbtiles`. Si el mapa está en otra ruta, preparar una carpeta de transferencia con la API detenida; incluir archivos WAL/SHM de la base al copiarla.
3. Antes del primer `iniciar`, ejecutar `./quibar importar-datos /ruta/datos`. No admite un volumen poblado, ni siquiera si solo contiene una base de demostración. La importación se ejecuta con privilegios dentro del contenedor para leer datos nativos restringidos y deja propietario 10001 para la aplicación.
4. Se toma una copia consistente por la API de SQLite, se preservan fotos y mapa, y se guarda `pre-migration.tar.gz` dentro del volumen antes de aplicar Alembic. El origen se monta en modo lectura y se conserva intacto. Si falla una migración, detenerse y recuperar ese respaldo; no eliminar los datos originales.
5. Ejecutar `iniciar`, revisar comercios, usuarios y mapa. El importador no lee automáticamente `.env` ni traslada contraseñas de Ollama o configuración del sistema.

Los enlaces simbólicos en fotos se rechazan. El importador no realiza una sincronización continua. Si ya se inició una base nueva, usar otro proyecto/volumen de destino explícitamente; no borrar el volumen por ensayo y error.

## Respaldar, actualizar y recuperar

`./quibar respaldo` pausa API/limpieza, guarda SQLite (incluyendo WAL), fotos y mapa en `backups/FECHA.tar.gz` y reinicia solo los servicios que estaban activos. No sobreescribe archivos existentes. Guardar también `.quibar/*.env` de forma privada. Una interrupción puede dejar un archivo incompleto: comprobar el resultado antes de usarlo.

Antes de actualizar código o migraciones, crear un respaldo; después ejecutar `iniciar`. Los volúmenes sobreviven a reconstrucciones y a `detener`. No usar `docker compose down -v` en instalaciones con datos que se quieran conservar.

Para recuperar, conservar la versión de código correspondiente y extraer un respaldo confiable en una carpeta privada con `quibar.sqlite3`, `media/` y `map.mbtiles`. Importarlo en un volumen nuevo con `importar-datos`, verificarlo y cambiar al nuevo proyecto. Mantener el volumen anterior hasta confirmar la recuperación. No extraer archivos de procedencia desconocida.

Para un proyecto nuevo explícito, los operadores pueden usar Compose directamente con `-p NOMBRE --env-file CONFIG -f compose.yaml --profile tools`; la importación usa `run --rm --no-deps --user 0:0 -v CARPETA:/import:ro tools python -m backend.container_ops import /import`. El lanzamiento de ese proyecto debe mantener el mismo nombre y configuración. Los lanzadores habituales usan los nombres fijos `quibar`/`quibar-dev`.

## Verificación

`./quibar probar` ejecuta las suites de backend e interfaz dentro de imágenes Docker. `ops/docker/acceptance.sh` comprueba HTTP real, moderación, HTTPS/CSRF, fallback y persistencia tras recrear contenedores en un proyecto temporal, que elimina al terminar. No descarga el modelo de 14B ni utiliza datos reales. CI ejecuta esta aceptación y analiza la sintaxis PowerShell. La ejecución real en macOS/Windows y las pruebas físicas de GPU, táctil, QR y reinicio del kiosco requieren esos equipos.

Las operaciones del lanzador se serializan mediante `.quibar/NOMBRE.lock`. Si un cierre forzado deja ese directorio, comprobar que no exista otra operación antes de retirarlo manualmente.

## Mapa del circuito y servicios locales

Consulta [Santa Bárbara–Huequecura–Ralco](map-circuit.md) para instalar mapas raster y datos viales, configurar el origen, moderar atractivos y operar Valhalla/Piper. `respaldo` incluye `routing/` con el motor detenido; el modelo de voz se mantiene en su propio volumen.
