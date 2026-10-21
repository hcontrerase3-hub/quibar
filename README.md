# Quíbar · Guía comercial local

Tótem táctil para descubrir comercios de Quilaco y Santa Bárbara. El catálogo, el panel administrativo y los mapas funcionan en el tótem; el asistente puede usar Ollama en el mismo equipo o en un servidor privado del cliente. **Las ocho fichas incluidas son ficticias**; la mascota de Quíbar fue aportada por Hugo.

El stack sigue las guías 2.2 y 2.3: **React + Vite + TypeScript + Tailwind CSS**, FastAPI, SQLAlchemy/Alembic, SQLite WAL/FTS5, Leaflet, `qrcode.react` y Ollama/Qwen 3. En producción FastAPI entrega la SPA compilada; Node se usa solo para desarrollo y compilación; Docker incluye estas herramientas.

## Iniciar con Docker (recomendado)

Instala Docker Desktop en Windows/macOS o Docker Engine con Compose v2 en Linux. No necesitas instalar Node, Python ni Ollama en el equipo anfitrión.

```bash
./quibar iniciar       # macOS / Linux: http://127.0.0.1:8000
./quibar desarrollar   # desarrollo con recarga: http://127.0.0.1:3000
./quibar detener      # conserva todos los datos
```

En Windows usa `quibar.cmd iniciar`, `quibar.cmd desarrollar` y `quibar.cmd detener` desde PowerShell o CMD, con Docker Desktop en modo de contenedores Linux. El primer arranque pide crear un administrador; también puedes hacerlo con `./quibar admin`. No hay usuarios ni contraseñas predeterminados.

La configuración se crea en `.quibar/production.env` o `.quibar/development.env`, sin modificar `.env`. Ambos entornos tienen volúmenes separados; la API de desarrollo usa el puerto 8001. La descarga inicial de Qwen 3 puede tardar y requiere espacio para unos 9,3 GB de modelo, además de las imágenes. Mientras se prepara o si falla, el catálogo y el chat básico siguen disponibles. Sigue el progreso con `./quibar logs model-init`.

| Acción | Comando (Windows: sustituir `./quibar` por `quibar.cmd`) |
|---|---|
| Pruebas backend e interfaz en contenedores | `./quibar probar` |
| Registros | `./quibar logs` |
| Crear primer administrador | `./quibar admin` |
| Restablecer contraseña | `./quibar admin reset-password CORREO` |
| Respaldo completo de base, fotos y mapa | `./quibar respaldo` |
| Instalar mapa | `./quibar importar-mapa /ruta/mapa.mbtiles` |
| Importar datos nativos en un volumen vacío | `./quibar importar-datos /ruta/datos` |

Para administrar el entorno de desarrollo, antepone `--dev`: `./quibar --dev detener`, `./quibar --dev admin`, etc. `detener` nunca elimina volúmenes. Los respaldos se guardan en `backups/`, pausando temporalmente la API y la limpieza para mantener coherencia. Conserva la configuración por separado. La importación requiere detener previamente los servicios nativos y un destino vacío; no copia datos automáticamente al iniciar. Consulta [operación, migración y recuperación](docs/docker.md).

El modo predeterminado ejecuta Ollama por CPU dentro de Docker. Para reutilizar Ollama instalado en el anfitrión, cambia `QUIBAR_OLLAMA_MODE=native` en la configuración correspondiente. Linux usa la red del anfitrión solo para el cliente de IA; macOS/Windows usan `host.docker.internal`. La API continúa entrando por el socket privado de Nginx. La aceleración GPU y el tiempo de respuesta deben medirse en el equipo final. También puedes configurar `QUIBAR_OLLAMA_MODE=remote`, `OLLAMA_URL=http://IP-TAILSCALE:11434` y un `QUIBAR_MODEL` ya instalado. Ese modo está disponible también para producción y para inferencia en el datacenter del cliente. Verifica y precarga el modelo sin descargarlo; requiere acceso al servidor por la red privada.

## Preparar el entorno nativo (alternativa)

Se recomienda Python 3.12 y Node.js 22.13 o posterior. Para IA local, instala Ollama y descarga el modelo acordado (aproximadamente 9,3 GB):

```bash
ollama pull qwen3:14b-q4_K_M
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm ci
```

Copia `.env.example` a `.env` **si todavía no existe**. Ahí puedes ajustar puertos, rutas y modelo. No publiques ese archivo. La descarga inicial de dependencias, del modelo y de cartografía requiere conexión; la atención local no usa proveedores de IA en la nube.

## Ejecutar localmente

```bash
npm run build
.venv/bin/python -m backend.cli migrate
.venv/bin/python -m backend.cli create-admin operador@example.com --name 'Administrador local'
npm start
```

Abre `http://127.0.0.1:8000/` para el tótem y `/admin` para administrar. La creación del usuario pide una contraseña de al menos 12 caracteres; no existen credenciales predeterminadas. `npm start` usa el host y puerto de API configurados en `.env`.

Para desarrollar, inicia `.venv/bin/python -m backend.run` en una terminal y `npm run dev` en otra. Vite usa `127.0.0.1:3000` y envía `/api`, `/media` y `/tiles` a FastAPI. El iniciador `./iniciar-quibar.command` prepara la compilación, precarga Ollama y abre el tótem en macOS.

## Catálogo y administración

- Un **Administrador** crea usuarios y aprueba, edita o suspende fichas. Un **Operador Territorial** prepara fichas y fotografías para revisión; sus cambios se guardan pendientes. Solo los registros aprobados de rubros activos son públicos y elegibles para Quíbar.
- Las fichas reales requieren coordenadas y contacto verificados antes de aprobarse. Los ejemplos migrados conservan su información original: no se inventan ubicaciones, teléfonos ni fotos.
- Las imágenes se guardan como WebP local, sin metadatos originales: máximo ocho por ficha, 8 MB y 20 megapíxeles por archivo. Se pueden ordenar, seleccionar como portada y añadir texto alternativo.
- Los cambios generan auditoría con datos anteriores y posteriores. Las métricas son anónimas y se conservan durante 90 días; `QR_MOSTRADO` mide la visualización del código, no confirma su escaneo.
- El catálogo abierto se actualiza cada cinco segundos. Si la API falla, la interfaz muestra la indisponibilidad; no vuelve a publicar una copia estática de fichas suspendidas.

`data/catalog.json` es la semilla inicial. Alembic carga esos registros solo al crear la base; si encuentra la tabla antigua `businesses`, importa sus datos y conserva esa tabla. **No elimines la base para actualizar el catálogo**. En una instalación existente, realiza un respaldo antes de migrar:

```bash
.venv/bin/python -m backend.cli backup /tmp/quibar-respaldo.sqlite3
.venv/bin/python -m backend.cli migrate
```

## Mapas y QR

Leaflet obtiene teselas raster del archivo MBTiles local indicado por `QUIBAR_TILES_PATH`. Para instalar un paquete de la zona, con licencia que permita su uso local:

```bash
.venv/bin/python -m backend.cli import-map /ruta/quilaco-santa-barbara.mbtiles
```

El importador verifica integridad y formato (PNG/JPEG/WebP), y sustituye el archivo de forma atómica. Para cambiar un mapa existente, añade `--replace`. Conserva la atribución y procedencia del paquete. No se descargan automáticamente teselas desde el servicio público de OpenStreetMap.

Las fichas con coordenadas muestran ubicación y QR de ruta. Un QR separado permite abrir WhatsApp cuando existe un contacto. La generación no necesita internet; la navegación y mensajería del teléfono dependen de sus aplicaciones, mapas descargados y conectividad. Si falta cartografía o coordenadas, la interfaz lo indica.

## Asistente con Ollama

FastAPI recupera como máximo tres fichas aprobadas mediante búsqueda normalizada y ranking FTS5. Envía su contenido a Ollama; valida IDs, nombres y datos numéricos de la respuesta. Si la consulta no tiene coincidencias, evita la generación abierta. Si el modelo falla o supera el plazo configurado, devuelve una respuesta básica con datos del catálogo.

El plazo recomendado es de seis segundos (`QUIBAR_MODEL_TIMEOUT`); la interfaz limita la espera a doce segundos. `QUIBAR_MODEL_KEEP_ALIVE=-1` mantiene el modelo cargado en el equipo dedicado. La validación reduce invenciones, pero **no demuestra una tasa de alucinación cero**. El requisito de respuesta inferior a cinco segundos debe medirse con Qwen 3 y el hardware final; no está garantizado por el código.

## Comprobaciones

```bash
npm test
npm run build
.venv/bin/python -m unittest backend.test_quibar backend.test_stack -v
curl -s http://127.0.0.1:8000/api/quibar/health
curl -s -X POST http://127.0.0.1:8000/api/quibar/chat \
  -H 'Content-Type: application/json' -d '{"query":"Un café en Quilaco"}'
```

Las pruebas usan bases temporales y transportes de IA simulados; no modifican el catálogo local ni necesitan Ollama. GitHub Actions ejecuta ambas suites y compila la SPA. Para mantenimiento están disponibles `backend.cli reset-password`, `backup`, `import-map` y `prune`.

## Despliegue y evidencia académica

Consulta [la instalación en Ubuntu y el modo kiosco](docs/deployment.md) y [la correspondencia con las guías y pruebas pendientes](docs/implementation-status.md). Los scripts preparan systemd, Chromium/Openbox y retención de datos. La administración remota se realiza por Tailscale Serve y ACL privadas; la API escucha únicamente en loopback.

Los archivos persistentes (`*.sqlite3*`, medios, cartografía), las credenciales y los entornos locales están excluidos de Git. Las fotografías de comercios suspendidos también quedan fuera del acceso público.
