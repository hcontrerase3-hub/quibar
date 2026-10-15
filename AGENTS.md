# Repository Guidelines

## Project Structure & Module Organization

The kiosk interface is a Next.js App Router application in `app/`; shared UI primitives are in `components/ui/`, and helpers are in `lib/`. The local FastAPI service lives in `backend/`: `app.py` defines the API, `db.py` handles SQLite, `rag.py` retrieves approved catalog entries, and `preload.py` prepares the local model. `data/catalog.json` is the demo catalog, while `public/` holds static assets. The database file is generated at `backend/quibar.sqlite3`; do not treat it as source data.

## Build, Test, and Development Commands

- `npm ci` installs the locked frontend dependencies; `npm run dev` starts Next.js on `127.0.0.1:3000`.
- `npm run build` creates the production build; `npm run start` serves it after building.
- `.venv/bin/python -m pip install -r backend/requirements.txt` installs API dependencies.
- `.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000` starts the local API. Ollama must be running with the configured model for local AI responses.

## Coding Style & Naming Conventions

Follow existing TypeScript conventions: strict typing, two-space indentation, React components in PascalCase, and variables/functions in camelCase. Keep page-specific styling in `app/` CSS files and reuse components from `components/ui/`. Python modules and functions use `snake_case`; keep API and database behavior in `backend/`. No formatter or linter script is configured in `package.json`, so match the surrounding code style.

## Testing Guidelines

Run the backend acceptance suite with `.venv/bin/python -m unittest backend.test_quibar -v`. It covers catalog approval, retrieval, and conversation follow-ups. For a running backend, check `curl -s http://127.0.0.1:8000/api/quibar/health`; exercise chat with the sample request in `README.md`. There is no separate frontend test script configured.

## Commit & Pull Request Guidelines

Recent commits use short subjects, with a mix of Spanish and English and no consistent prefix. Keep each commit focused and describe the change directly (for example, `Ajusta filtro de comuna`). Pull requests should summarize behavior changes, list relevant verification commands and results, and include a screenshot for visible kiosk UI changes. Link related issues when applicable.

## Security & Configuration Tips

The demo businesses and hours are fictional. Only approved SQLite records are exposed by the API; preserve that filter when changing catalog or retrieval behavior. Keep the app local: it is designed to use Ollama on the same machine and does not require cloud AI credentials. Do not commit secrets, generated databases, or virtual-environment files.
