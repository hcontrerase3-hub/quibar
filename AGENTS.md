# Repository Guidelines

## Project Structure & Module Organization

The React/Vite touchscreen SPA is in `app/`; reusable primitives are in `components/ui/` and helpers in `lib/`. FastAPI serves the compiled `dist/` in production. Backend modules cover public APIs, administration, sessions, maps, and SQLAlchemy access. Alembic revisions live in `backend/migrations/`. `data/catalog.json` seeds fictional demo records; `public/` contains assets. Docker configuration lives in `compose*.yaml`, `Dockerfile`, and `ops/docker/`. Ubuntu kiosk scripts and systemd units are in `ops/`; operational guides are in `docs/`.

## Build, Test, and Development Commands

- `./quibar iniciar` builds and starts production at `127.0.0.1:8000`; `./quibar desarrollar` starts Vite with reload at port 3000 and a separate API/data environment.
- `./quibar detener` stops services while preserving volumes. Prefix actions with `--dev` to select development.
- `./quibar admin` creates the first administrator interactively. `./quibar respaldo` backs up database, media, and map with writers paused.
- `./quibar probar` runs backend and frontend suites inside containers. `ops/docker/acceptance.sh` checks HTTP and persistence using disposable volumes.
- On Windows, replace `./quibar` with `quibar.cmd`. Docker is the only application runtime prerequisite.
- Native alternative: `npm ci`, `npm run dev`, `npm run build`, and `.venv/bin/python -m backend.run`; install Python dependencies from `backend/requirements.lock`.

## Coding Style & Naming Conventions

Use strict TypeScript, two-space indentation, PascalCase components, and camelCase functions. Python uses four-space indentation and snake_case; domain entities follow the Spanish academic model while public API fields remain English. Reuse UI primitives and surrounding patterns; no formatter/linter script is configured.

## Testing Guidelines

Tests use unittest (`backend.test_quibar`, `backend.test_stack`, `backend.test_container`) and Vitest (`*.test.tsx`). Use temporary databases and simulated model transports. Cover approval, migrations, roles, CSRF, media, and retrieval when modifying those behaviors. Physical touch, QR scanning, recovery, and model latency require target hardware.

## Commit & Pull Request Guidelines

Use short, direct Spanish or English subjects and focused commits per functional phase. Describe behavior, verification results, related issues, and screenshots for UI changes.

## Security & Data Preservation

Publish only approved records from active categories. Preserve authentication, CSRF, loopback ingress, and the private proxy socket. Never commit `.env`, `.quibar/`, generated databases, uploads, maps, backups, or credentials. Keep development and production volumes separate; never delete populated volumes to migrate data. Follow `docs/docker.md` for explicit imports and recovery.
