# Repository Guidelines

## Project Structure & Module Organization

The touchscreen React SPA is in `app/`, with shared primitives in `components/ui/` and helpers in `lib/`. Vite compiles it into `dist/`; FastAPI serves that build in production. Backend modules live in `backend/`: `app.py` handles chat, `admin.py` manages protected catalog operations, `security.py` handles sessions, and `db.py` provides SQLAlchemy access. Alembic revisions are in `backend/migrations/`. `data/catalog.json` seeds the fictional demo records; `public/` contains static assets. Deployment scripts and systemd units are in `ops/`; operational documentation is in `docs/`.

## Build, Test, and Development Commands

- `npm ci` installs locked frontend dependencies; `npm run dev` starts Vite at `127.0.0.1:3000` with API, media, and tile proxies.
- `npm run build` checks TypeScript and creates the SPA; `npm start` serves it through FastAPI at the configured local address.
- `.venv/bin/python -m pip install -r backend/requirements.lock` installs the verified Python environment.
- `.venv/bin/python -m backend.run` starts the API; `backend.cli migrate` applies migrations and `backend.cli create-admin EMAIL --name NAME` provisions the first administrator.
- `npm test` runs Vitest interaction tests. `.venv/bin/python -m unittest backend.test_quibar backend.test_stack -v` runs backend acceptance tests.

## Coding Style & Naming Conventions

Use strict TypeScript, two-space indentation, PascalCase components, and camelCase functions. Reuse UI primitives and keep app styles in `app/`. Python uses four-space indentation and snake_case; relational entity names follow the Spanish academic model, while public API fields retain their established English names. No formatter or lint script is configured; follow surrounding patterns.

## Testing Guidelines

Use temporary databases and simulated model transports. Cover approval filtering, migrations, roles, sessions, media, and conversation follow-ups when changing those behaviors. Tests use `test_*.py` and `*.test.tsx`. Run affected suites and the production build for frontend changes. Physical touch, QR scanning, kiosk recovery, and model latency need validation on the target hardware.

## Commit & Pull Request Guidelines

Use short, direct commit subjects in Spanish or English. Keep commits focused by functional phase. Pull requests should describe behavior changes, verification results, related issues, and screenshots for visible UI changes.

## Security & Configuration Tips

Only approved records from active categories may be public or retrieved by Quíbar. Administrative writes require authentication, network restrictions, and CSRF protection. Keep secrets in local `.env` files. Never commit generated databases, media uploads, MBTiles, environments, or credentials. Preserve existing data through migrations and backups; do not reset SQLite to update the catalog.
