# Quíbar · IA local para tótem

Prototipo académico interactivo para descubrir PYMEs de Quilaco y Santa Bárbara. **Los ocho negocios, servicios y horarios son ficticios.** Utiliza la imagen de Quíbar proporcionada por Hugo.

## Instalar por primera vez en macOS

1. Instala [Node.js](https://nodejs.org/) 22.13 o posterior y [Python](https://www.python.org/downloads/) 3.10 o posterior si todavía no los tienes.
2. Instala la aplicación [Ollama para macOS](https://ollama.com/download/mac), ábrela y acepta instalar su comando de Terminal. Requiere macOS 14 o posterior.
3. Copia `.env.example` como `.env` y ajusta ahí los puertos, la URL de Ollama y el modelo si es necesario. El modelo indicado en el informe está configurado en `QUIBAR_MODEL` (aproximadamente 9,3 GB; es una descarga única):

   ```bash
   ollama pull qwen3:14b-q4_K_M
   ```

4. Descomprime `Quibar-IA-local-v6.zip`. En Terminal, entra a la carpeta `quibar-ia-local-v6` y ejecuta:

   ```bash
   chmod +x iniciar-quibar.command
   ./iniciar-quibar.command
   ```

   Si el ZIP quedó en Descargas, puedes usar `cd ~/Downloads/quibar-ia-local-v6` antes de esos dos comandos.

El iniciador instala las dependencias de Node y Python la primera vez, prepara la página, **carga el modelo local antes de abrir el tótem**, inicia FastAPI y abre `http://localhost:3000/` en modo tótem si Chrome está instalado. La carga inicial puede tardar; la Terminal muestra si la IA quedó lista o por qué Ollama no pudo cargarla. Mantén la ventana de Terminal abierta. `Ctrl+C` detiene los servidores. Si Ollama no está listo, el catálogo y las respuestas básicas siguen funcionando.

Si macOS bloquea el doble clic sobre el archivo `.command`, ejecuta los comandos anteriores desde Terminal. Si el modelo de 14B no cabe cómodamente en el Mac, instala `ollama pull qwen3:4b` y cambia `QUIBAR_MODEL` a `qwen3:4b` en `.env` como variante de demostración.

## Iniciar manualmente

Desde la carpeta del proyecto, con Ollama abierto y el modelo descargado, usa dos ventanas de Terminal:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m backend.preload
set -a; . ./.env; set +a
.venv/bin/python -m uvicorn backend.app:app --host "$QUIBAR_API_HOST" --port "$QUIBAR_API_PORT"
```

En la segunda ventana:

```bash
npm ci
npm run build
set -a; . ./.env; set +a
./node_modules/.bin/next start --hostname "$QUIBAR_WEB_HOST" -p "$QUIBAR_WEB_PORT"
```

Abre `http://localhost:3000/`. La página, la API, Ollama y SQLite están configurados para el mismo computador. La aplicación no requiere claves ni proveedores de IA en la nube; la descarga inicial de Ollama, el modelo y las dependencias sí requiere conexión a Internet.

## Cómo funciona

1. Las fichas de ejemplo se cargan desde `data/catalog.json` a `backend/quibar.sqlite3` al primer inicio. Solo los registros con estado `Aprobado` aparecen en `/api/quibar/catalog` y pueden ser recuperados para una respuesta.
2. `backend/rag.py` encuentra hasta tres fichas pertinentes por nombre, rubro, comuna y servicios. Si la consulta menciona un nombre o servicio que no figura, Quíbar reconoce la ausencia de ese registro.
3. `backend/app.py` envía únicamente los datos aprobados recuperados y el contexto reciente a Ollama. Qwen3 selecciona IDs de fichas y **redacta una respuesta breve y natural** dentro de un esquema JSON. El servidor valida los IDs, nombres y datos numéricos antes de mostrarla. Si falla la validación, utiliza una respuesta compuesta con SQLite. Los saludos como “Hola” se responden con el modelo sin inventar negocios.
4. Las preguntas de seguimiento usan las fichas de la respuesta anterior. Si Ollama falla o tarda más del límite, se responde en modo básico. La interfaz distingue “IA local” de “Modo básico” para no atribuir al modelo una respuesta de respaldo. La carga previa y la espera ampliada permiten que el modelo de 14B responda en equipos donde tarda más de ocho segundos.

La validación automática reduce riesgos, pero el texto generado podría contener afirmaciones difíciles de comprobar mecánicamente. Antes de uso público, comprueba manualmente la batería de 10 preguntas con el modelo y el catálogo reales. La meta de menos de 5 segundos se mide sobre el hardware final.

La base SQLite se crea en `backend/quibar.sqlite3`; para restablecer los ocho ejemplos, detén el servidor y elimina ese archivo. El JSON del paquete es el catálogo de demostración inicial. Para probar la aprobación, cambia el estado de un registro en SQLite, reinicia el servidor y actualiza la página. No hay un panel de administración en esta versión.

## Probar los flujos

```bash
.venv/bin/python -m unittest backend.test_quibar -v
curl -s "http://127.0.0.1:${QUIBAR_API_PORT:-8000}/api/quibar/health"
curl -s -X POST "http://127.0.0.1:${QUIBAR_API_PORT:-8000}/api/quibar/chat" \
  -H 'Content-Type: application/json' \
  -d '{"query":"Un café en Quilaco"}'
```

La última respuesta debe indicar `mode: "ia_local"` cuando Qwen3 esté funcionando y responda a tiempo, o `mode: "basico"` si está desconectado. Prueba también “¿Conoces Hotel Estrella Austral?” para verificar una ausencia y “¿Y su horario?” después de abrir una ficha mediante la conversación.

Prueba “Hola” para verificar un saludo redactado por la IA (`mode: "ia_local"`, sin fichas), seguido de “Quiero tomar un café en Quilaco” y “¿Y su horario?”.

El objetivo académico de respuesta inferior a cinco segundos requiere **medición en el Mac y tótem finales**: depende del tiempo de carga del modelo y de sus recursos. El servidor espera hasta 110 segundos por Ollama antes de pasar al modo básico; la página espera hasta 120 segundos y el puente local hasta 125. La primera carga puede ser mucho más lenta que las consultas posteriores. El paquete no incluye el modelo descargado.

## Archivos principales

- `app/page.tsx`, `app/kiosk.css`: interfaz táctil, conversación, filtros y fichas.
- `data/catalog.json`: ocho fichas ficticias marcadas como ejemplo y aprobadas.
- `backend/db.py`, `backend/rag.py`, `backend/app.py`: SQLite, recuperación y API local con Ollama.
- `backend/test_quibar.py`: preguntas de aceptación, seguimiento y exclusión de fichas suspendidas.
- `public/quibar-angostura-original.png`: mascota aportada para el proyecto.
