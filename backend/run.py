"""Servidor local de producción; lee la configuración del archivo .env."""
import os
import uvicorn
from .db import ROOT  # loads the trusted local .env without overriding environment variables

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host=os.environ.get("QUIBAR_API_HOST", "127.0.0.1"),
                port=int(os.environ.get("QUIBAR_API_PORT", "8000")),
                proxy_headers=True, forwarded_allow_ips="127.0.0.1,::1")
