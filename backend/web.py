"""Entrega de la SPA compilada por Vite desde el mismo origen que la API."""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .db import ROOT

router = APIRouter()


@router.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    if path.split("/")[0] in {"api", "media", "tiles"}:
        raise HTTPException(404, "Recurso no encontrado")
    root = Path(os.environ.get("QUIBAR_DIST_DIR", str(ROOT / "dist"))).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(404)
    if target.is_file():
        return FileResponse(target)
    # SPA routes only; don't return index.html for missing image or JS assets.
    if "." in Path(path).name:
        raise HTTPException(404)
    index = root / "index.html"
    if not index.is_file():
        raise HTTPException(503, "Compila la interfaz con npm run build")
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
