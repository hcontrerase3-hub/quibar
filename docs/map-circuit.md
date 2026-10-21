# Mapa y recorridos Santa Bárbara–Huequecura–Ralco

## Experiencia

El mapa es la pantalla inicial. Los filtros distinguen sector turístico y tipo de lugar; la comuna administrativa se conserva por separado (incluido Alto Biobío). Quilaco permanece en la base histórica y el API anterior, fuera del circuito principal. Una ficha puede consultarse sin ubicación, pero solo las coordenadas verificadas de lugares reales aparecen como puntos y permiten calcular rutas.

Selecciona un destino y pulsa **Cómo llegar**. Elige caminar o conducir; las indicaciones, distancia y tiempo estimado proceden de Valhalla local, sin tráfico en tiempo real. Quíbar comprueba hasta diez candidatos próximos al trazado y propone como máximo tres paradas, con diversidad de categorías. El desvío máximo por parada es 5 minutos a pie o 10 en vehículo, ajustable mediante `QUIBAR_WALK_DETOUR_MIN` y `QUIBAR_DRIVE_DETOUR_MIN`.

Una sugerencia no modifica el recorrido: **Añadir parada** confirma el cambio. Las paradas se insertan en el tramo correspondiente, manteniendo las ya confirmadas. El QR conserva origen, modalidad, destino y hasta tres paradas; Google Maps recalcula la navegación en el teléfono y puede requerir conexión. No se promete que reproduzca exactamente la geometría de Valhalla.

La presentación básica es inmediata. Ollama puede mejorar el texto desde el servidor privado del cliente sin decidir caminos ni incorporar lugares no aprobados. **Escuchar a Quíbar** solicita voz local; no se reproduce automáticamente. Cambiar de recorrido o volver al inicio detiene el audio. La sesión se restablece después de 60 segundos sin interacción.

## Preparar una instalación real

No se incluyen ubicaciones ficticias en el mapa ni datos viales de demostración en producción. La semilla comercial conserva sus ocho fichas ficticias; las del circuito se identifican como ejemplos en la lista. Para operar se necesitan los siguientes datos, verificados por el equipo territorial:

1. Iniciar con `./quibar iniciar` (Windows: `quibar.cmd iniciar`) y crear el administrador con `./quibar admin` si falta. Para conservar una instalación nativa, importar sus datos antes del primer inicio, siguiendo `docs/docker.md`.
2. En **Administración → Atractivos y tótem**, registrar la ubicación física del equipo, su fuente y la confirmación de verificación. Debe estar dentro del circuito.
3. Editar los comercios reales con sector, coordenadas, fuente y ubicación verificada. En atractivos registrar descripción, categoría, comuna, sector, coordenadas, acceso, fuente y verificación del acceso. El operador prepara fichas pendientes; el administrador aprueba o suspende. No asumir horarios vigentes ni apertura basándose solo en texto libre.
4. Obtener un MBTiles **raster PNG/JPEG/WebP**, con licencia, atribución y cobertura del circuito. Instalarlo con `./quibar importar-mapa /ruta/circuito.mbtiles`. No usar teselas vectoriales ni descargar masivamente el servicio público de teselas de OpenStreetMap.
5. Obtener una extracción **OpenStreetMap `.osm.pbf`** que incluya Santa Bárbara, Huequecura, Ralco y sus caminos de conexión, puentes y accesos circundantes. Una extracción regional del Biobío es apropiada; una caja recortada demasiado estrecha puede romper caminos. La extracción puede prepararse previamente en otro equipo: el tótem no necesita descargar Chile completo.
6. Ejecutar `./quibar preparar-rutas /ruta/region.osm.pbf`. El comando pausa el motor, importa el archivo, conserva datos previos al reemplazar y arranca la construcción de Valhalla. Seguir `./quibar logs routing`. Una actualización requiere respaldo previo y `--replace`.
7. Validar caminos y accesos reales en terreno con ambos perfiles. Un lugar a menos de 300 m (a pie) o 1 km (vehículo) del trazado solo se recomienda si el motor confirma un desvío vial válido dentro del tiempo permitido.

El mapa raster y el grafo vial son paquetes distintos. Instalar un MBTiles no instala rutas; importar un PBF no genera el mapa visual. La cobertura visual inicial es un encuadre del circuito, no la ubicación de un establecimiento. Las coordenadas exactas del tótem y de cada lugar requieren verificación propia. La extracción y el paquete raster deben acompañarse de procedencia, fecha y atribución; no se declaran preparados cuando no están instalados.

Los servicios principales arrancan aunque falten cartografía, grafo, voz u Ollama. Sin mapa se muestra un aviso y la lista; sin origen verificado no se solicita una ruta; sin camino válido se informa la limitación y no se dibuja una línea recta como carretera.

## Servicios y datos persistentes

- `routing`: imagen oficial de Valhalla fijada por digest, dos hilos, sin puerto publicado por defecto. Espera un PBF en `/state/routing` y construye el grafo allí. No descarga datos viales ni reconstruye desde un ejemplo al iniciar. El paquete es diferente en desarrollo y producción.
- `speech`: Piper 1.3.0 por CPU con dos hilos y dependencias fijadas. Descarga una vez `es_ES-davefx-medium`, su configuración y ficha desde la versión `v1.0.0` de `rhasspy/piper-voices`. Después funciona sin red. Es una voz española; no se presenta como grabación humana o voz chilena personalizada. Los textos y WAV se cachean solo en memoria, con límites.
- `state`: base, fotos, mapa y `routing/`. `./quibar respaldo` pausa API, limpieza y motor vial para copiar coherentemente estos datos y restaura los servicios que estaban activos. Los grafos previos se conservan en `routing.previous-*`; no se eliminan automáticamente.
- `voices`: modelo de voz independiente; puede descargarse nuevamente a partir de la versión fijada. Las recomendaciones y las grabaciones de visitantes no se guardan en disco.

Con Ollama nativo en Linux, la API usa red de anfitrión para alcanzarlo. Ese override publica **solo en loopback** el motor en 18002 y la voz en 15000; el desarrollo usa 18003/15001. La entrada de FastAPI sigue siendo un socket privado. En modo Ollama remoto no se necesitan esos puertos publicados.

## API y consistencia

- `GET /api/quibar/places`: lugares públicos, sectores, encuadre y ubicación pública del tótem. Los lugares sin verificación no exponen coordenadas de mapa.
- `POST /api/quibar/routes`: `{destination:"interest:ID", profile:"walking"|"driving", stops:[]}`. Valida origen y lugares; devuelve geometría vial, indicaciones, estimaciones, texto básico y referencia temporal de narración.
- `POST /api/quibar/routes/suggestions`: mismo recorrido; devuelve paradas elegibles, desvíos, orden de inserción y narración básica.
- `POST /api/quibar/routes/narration`: mismo recorrido más IDs de sugerencias; el servidor vuelve a comprobar su elegibilidad antes de solicitar redacción a Ollama. Si falla, conserva el texto determinista.
- `POST /api/quibar/routes/speech`: referencia temporal de narración emitida por el servidor; no acepta texto arbitrario del visitante. Revalida los lugares y entrega WAV o un error que no bloquea el mapa.
- Administración autenticada: `/api/quibar/admin/interests` y `/api/quibar/admin/station`, con roles, CSRF y auditoría. Los comercios añaden sector y verificación geográfica sin romper el catálogo anterior.

Las ediciones, suspensiones y cambios de origen invalidan recorridos o audios anteriores. La interfaz actualiza el catálogo cada cinco segundos y cancela solicitudes al cambiar de destino. Los caches de cálculo y narración son acotados; una referencia de audio vence a los 15 minutos o al reiniciar la API.

## Comprobación

`./quibar probar` ejecuta backend e interfaz sin instalar herramientas en el anfitrión. `ops/routing/acceptance.sh` construye un grafo OSM **sintético** exclusivamente en un proyecto temporal y comprueba Valhalla real, ambos perfiles, sugerencias, confirmación de paradas, voz WAV por el proxy, revocación y respaldo. Nunca carga esos lugares en producción y elimina únicamente su proyecto de prueba.

La revisión visual cubre escritorio y móvil con capturas identificadas como datos sintéticos o estados sin mapa. La cobertura cartográfica real, precisión de accesos, latencia del hardware, sonido del tótem, pantalla táctil y escaneo con teléfono se validan en la instalación destino.
