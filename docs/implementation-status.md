# Correspondencia de Quíbar con las guías 2.2 y 2.3

Actualización de implementación del 20 de octubre de 2026. El stack seleccionado guía el código del repositorio; las validaciones de hardware y servicios externos requieren el mini PC y las cuentas del equipo responsable.

| Componente de las guías | Implementación entregada | Evidencia |
|---|---|---|
| React, Vite, TypeScript y Tailwind | SPA táctil; compilación estática entregada por FastAPI | `npm run build`, `npm test` |
| FastAPI y Uvicorn | API local y archivos compilados en el mismo origen | Salud, catálogo, chat y administración |
| SQLAlchemy y Alembic | Modelo relacional y migraciones del catálogo anterior | Migración de datos y suite backend |
| SQLite WAL y FTS5 | Transacciones, claves foráneas e índice sincronizado | Pruebas de WAL, búsqueda y moderación |
| Administración y Argon2id | Roles, sesiones opacas, CSRF y usuarios sin contraseña predeterminada | Pruebas de autenticación, permisos y revocación |
| Catálogo y fotografías | CRUD, moderación y WebP local | Pruebas de publicación y acceso a medios |
| Leaflet y OpenStreetMap | Servidor local de MBTiles raster e importador atómico | Pruebas de teselas; paquete territorial por instalar |
| QR | Códigos separados de ruta y WhatsApp | Prueba DOM; escaneo físico pendiente |
| Ollama y Qwen 3 | Integración REST, precarga, contexto aprobado y modo básico | Protocolo simulado y validación; rendimiento real pendiente |
| Auditoría y métricas | Registro de cambios de solo anexado y uso anónimo | Pruebas de auditoría y estadísticas |
| Docker Compose y Nginx | Imagen multietapa, API sin puerto TCP, datos persistentes, desarrollo con recarga y lanzadores Windows/macOS/Linux | Aceptación en Linux; ejecución real Windows/macOS pendiente |
| Ubuntu, Openbox, Chromium y systemd | Instalador Docker y navegador en el anfitrión | Sintaxis y simulación de instalación; validación en mini PC pendiente |
| Tailscale/WireGuard | Administración privada con Serve y ACL documentadas | Activación con cuenta autorizada pendiente |
| Git y GitHub Actions | Commits por fase y workflow de backend, frontend y compilación | Ejecución local aprobada; ejecución remota depende de publicar el repositorio |

Verificación local final: 26 pruebas de backend y 5 de interfaz aprobadas, más 4 pruebas del lanzador, compilación TypeScript/Vite, sintaxis de los scripts y simulación del instalador correctas. Una instancia con datos temporales también entregó la SPA y la API por HTTP, autenticó una sesión y respondió en modo básico al no disponer de Ollama. `npm audit` no reportó vulnerabilidades después de actualizar la dependencia transitiva afectada.

Se añadió un anexo de implementación con respaldo previo a las fuentes Markdown de los informes 2.2 y 2.3 y a la planificación local de la Guía 2.1. Los DOCX/PDF se conservan como versiones de diseño. El tablero externo de Planner no se modificó.

## Interfaces y modelo de datos

Se mantienen `/api/quibar/health`, `/api/quibar/catalog` y `/api/quibar/chat`. El panel usa `/api/quibar/admin/*` para sesiones, usuarios, fichas, fotografías, auditoría y métricas. Las teselas están en `/tiles/{z}/{x}/{y}` y las fotografías en `/media/{archivo}`; una fotografía deja de ser pública cuando su ficha se suspende.

El modelo implementa comuna, rubro, comercio, fotografia_comercio, usuario_admin, registro_auditoria y metrica_evento, y añade sesion_admin para sesiones revocables. La clave interna de comercio es entera; `public_id` conserva los IDs de demostración utilizados por la API. Los campos públicos se serializan en inglés por compatibilidad con el prototipo. Razón social, RUT y antecedentes de usuarios no aparecen en el catálogo público.

Las coordenadas pueden quedar vacías durante la preparación y en datos de demostración migrados. Para aprobar una ficha real, la API exige coordenadas y WhatsApp verificados. `QR_MOSTRADO` mide exposición del código; no se declara un escaneo que el tótem no puede observar.

La búsqueda combina FTS5, normalización, palabras clave, comuna, rubro y contexto reciente. No utiliza embeddings ni una base vectorial. La respuesta generada se valida, pero la tasa cero de alucinaciones y la respuesta menor a cinco segundos siguen siendo objetivos que deben evaluarse empíricamente.

## Evidencia preparada para Planner

Sin conexión a Microsoft Planner desde esta sesión, estos estados se dejan listos para registrar; no se afirma que el tablero externo haya cambiado.

| Trabajo | Estado verificable |
|---|---|
| Migrar frontend a React/Vite y servir SPA desde FastAPI | Implementado y compilado |
| Implementar ORM, migraciones, SQLite WAL e índice FTS5 | Implementado y probado |
| Crear panel, roles, usuarios, auditoría y multimedia | Implementado y probado |
| Integrar mapas locales y QR | Código e importador probados; cartografía y teléfono de prueba pendientes |
| Preparar Linux/kiosco, systemd y red privada | Archivos entregados; instalación y verificación física pendientes |
| Medir latencia de Qwen 3 y recuperación del tótem | Pendiente de hardware final |

Las guías docentes PDF se mantienen como requisitos. Este anexo describe evidencia de implementación y debe acompañar las versiones académicas de los informes 2.2 y 2.3 para distinguir diseño, código y resultados medidos.

## Empaquetado Docker y entorno de desarrollo

Docker conserva React/Vite, FastAPI, SQLAlchemy/Alembic y SQLite WAL/FTS5. Node compila dentro de la imagen; Python 3.12 ejecuta la API sin privilegios. Nginx accede mediante socket Unix y publica solo loopback. Los datos y modelos usan volúmenes separados de las fuentes, con entornos independientes para desarrollo y producción. Los respaldos completos pausan escritores; la importación nativa verifica un destino vacío y conserva una copia previa a migrar.

La inferencia remota es una alternativa de producción para el datacenter del cliente cuando el tótem no tiene capacidad para el modelo. La IA admite tres modos: Ollama en Docker por CPU, Ollama en el anfitrión y un servidor privado remoto por Tailscale. La configuración actual usa un servidor remoto con `gemma4:e2b` ya instalado, sin descarga automática; esta elección no sustituye la validación pendiente de Qwen 3 de 14B en el mini PC ni demuestra funcionamiento de IA sin red cuando se usa un servidor remoto. Si la IA no responde, el modo básico permanece disponible.

La aceptación Docker verifica HTTP real, cookie HTTPS y CSRF, moderación, fallback, importación con permisos del usuario de aplicación, persistencia tras recreación y recarga Python/Vite. La descarga del modelo de 14B, la aceleración GPU, el kiosco físico y la ejecución en Windows/macOS requieren sus entornos correspondientes. Ver `docs/docker.md` y `docs/deployment.md`.

## Mapa principal del circuito Santa Bárbara–Huequecura–Ralco

Se incorporan sectores turísticos independientes de la comuna, Alto Biobío, atractivos moderados, origen verificado del tótem, rutas Valhalla peatonales y vehiculares, sugerencias con desvío vial, paradas confirmadas, QR con itinerario y voz Piper local. La inferencia Ollama remota sigue disponible para el datacenter del cliente. Las fichas anteriores se conservan y no reciben coordenadas inventadas.

La aceptación distingue datos sintéticos de datos territoriales: pruebas unitarias y HTTP usan bases temporales; el grafo de aceptación real de Valhalla es una cuadrícula explícitamente sintética. Antes de demostrar recorridos reales se deben instalar MBTiles y OSM PBF de la zona, verificar ubicaciones y accesos y medir el hardware. Ver `docs/map-circuit.md`.

Validación de esta fase: 39 pruebas backend, 7 de interfaz y 4 del lanzador aprobadas; compilación TypeScript/Vite y revisión visual en escritorio y móvil completadas. La aceptación Docker aprobó persistencia, respaldo, importación y recarga. La aceptación geográfica usó Valhalla y Piper reales: ambos perfiles, paradas confirmadas, revocación y audio WAV servido por el proxy. Estos resultados no verifican la precisión de datos territoriales todavía no instalados.
