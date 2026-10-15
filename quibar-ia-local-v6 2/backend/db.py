"""Catálogo local: solo registros Aprobado son visibles para Quíbar."""

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "backend" / "quibar.sqlite3"
SEED = ROOT / "data" / "catalog.json"


def db_path() -> Path:
    return Path(os.environ.get("QUIBAR_DB_PATH", str(DEFAULT_DB)))


def initialize() -> None:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS businesses (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            commune TEXT NOT NULL, area TEXT NOT NULL, summary TEXT NOT NULL,
            description TEXT NOT NULL, offerings TEXT NOT NULL, hours TEXT NOT NULL,
            keywords TEXT NOT NULL, visual TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('Pendiente', 'Aprobado', 'Suspendido')),
            demo INTEGER NOT NULL DEFAULT 1
        )""")
        if not conn.execute("SELECT 1 FROM businesses LIMIT 1").fetchone():
            records = json.loads(SEED.read_text(encoding="utf-8"))
            for record in records:
                conn.execute("""INSERT INTO businesses
                    (id,name,category,commune,area,summary,description,offerings,hours,keywords,visual,status,demo)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    record["id"], record["name"], record["category"], record["commune"],
                    record["area"], record["summary"], record["description"],
                    json.dumps(record["offerings"], ensure_ascii=False), record["hours"],
                    record["keywords"], record["visual"], record["status"], int(record["demo"]),
                ))
        conn.commit()


def approved() -> list[dict]:
    initialize()
    with closing(sqlite3.connect(db_path())) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM businesses WHERE status = 'Aprobado' ORDER BY name").fetchall()
    return [{**dict(row), "offerings": json.loads(row["offerings"]),
             "demo": bool(row["demo"])} for row in rows]
