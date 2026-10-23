"""Integración del stack: migración, moderación, sesiones y multimedia."""
from contextlib import closing
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from .app import app
from .db import approved, initialize, session
from .models import Comercio, Usuario
from .security import _attempts, create_user


class StackAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"QUIBAR_DB_PATH": f"{self.tmp.name}/db.sqlite3",
                                          "QUIBAR_ADMIN_NETWORKS": "127.0.0.0/8,::1/128,100.64.0.0/10",
                                          "QUIBAR_MEDIA_DIR": f"{self.tmp.name}/media",
                                          "QUIBAR_TILES_PATH": f"{self.tmp.name}/map.mbtiles"})
        self.env.start()
        _attempts.clear()
        initialize()
        create_user("admin@example.test", "Administración", "password-for-tests-123")
        create_user("operator@example.test", "Operación", "password-for-tests-123", "Operador Territorial")
        self.client = TestClient(app, client=("127.0.0.1", 50000))

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def login(self, email="admin@example.test"):
        response = self.client.post("/api/quibar/admin/session", json={"email": email, "password": "password-for-tests-123"})
        self.assertEqual(response.status_code, 200, response.text)
        self.csrf = {"x-csrf-token": response.json()["csrf"]}

    def row(self):
        rows = self.client.get("/api/quibar/admin/businesses").json()
        return next(r for r in rows if r["id"] == "grano-nativo")

    def test_migration_and_wal_preserve_demo(self):
        self.assertEqual(len(approved()), 8)
        initialize()
        self.assertEqual(len(approved()), 8)
        with closing(sqlite3.connect(os.environ["QUIBAR_DB_PATH"])) as db, db:
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(db.execute("SELECT version_num FROM alembic_version").fetchone()[0], "0004_demo_interests")
        self.assertNotIn("tax_id", self.client.get("/api/quibar/catalog").json()[0])

    def test_auth_network_csrf_logout_and_throttle(self):
        self.assertEqual(self.client.get("/api/quibar/admin/businesses").status_code, 401)
        remote = TestClient(app, client=("192.168.1.40", 1234))
        self.assertEqual(remote.post("/api/quibar/admin/session", json={"email": "x", "password": "bad"}).status_code, 422)
        self.assertEqual(remote.post("/api/quibar/admin/session", json={"email": "admin@example.test", "password": "bad"}).status_code, 403)
        remote.close()
        self.login()
        self.assertEqual(self.client.delete("/api/quibar/admin/session").status_code, 403)
        self.assertEqual(self.client.delete("/api/quibar/admin/session", headers=self.csrf).status_code, 200)
        self.assertEqual(self.client.get("/api/quibar/admin/session").status_code, 401)
        for _ in range(4):
            self.client.post("/api/quibar/admin/session", json={"email": "admin@example.test", "password": "bad"})
        self.assertEqual(self.client.post("/api/quibar/admin/session", json={"email": "admin@example.test", "password": "bad"}).status_code, 429)

    def test_moderation_roles_and_audit(self):
        self.login()
        row = self.row()
        row["status"] = "Suspendido"
        response = self.client.put(f"/api/quibar/admin/businesses/{row['id']}", json=row, headers=self.csrf)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(row["id"], {r["id"] for r in self.client.get("/api/quibar/catalog").json()})
        log = self.client.get("/api/quibar/admin/audit").json()[0]
        self.assertEqual(log["action"], "EDITAR")
        self.assertEqual(log["detail"]["before"]["status"], "Aprobado")
        self.login("operator@example.test")
        row["status"] = "Aprobado"
        self.assertEqual(self.client.put(f"/api/quibar/admin/businesses/{row['id']}", json=row, headers=self.csrf).status_code, 403)
        self.assertEqual(self.client.get("/api/quibar/admin/audit").status_code, 403)
        row["status"] = "Pendiente"
        self.assertEqual(self.client.put(f"/api/quibar/admin/businesses/{row['id']}", json=row, headers=self.csrf).status_code, 200)

    def test_image_reencoding_and_private_media(self):
        self.login()
        row = self.row()
        output = io.BytesIO()
        Image.new("RGB", (60, 40), "green").save(output, "PNG")
        response = self.client.post(f"/api/quibar/admin/businesses/{row['id']}/photos", headers=self.csrf,
                                    files={"file": ("test.png", output.getvalue(), "image/png")})
        self.assertEqual(response.status_code, 201, response.text)
        photo = response.json()["photos"][0]
        result = self.client.get(photo["url"])
        self.assertEqual(result.headers["content-type"], "image/webp")
        row["status"] = "Suspendido"
        self.client.put(f"/api/quibar/admin/businesses/{row['id']}", json=row, headers=self.csrf)
        self.client.delete("/api/quibar/admin/session", headers=self.csrf)
        self.assertEqual(self.client.get(photo["url"]).status_code, 404)
        self.login()
        self.assertEqual(self.client.get(photo["url"]).status_code, 200)

    def test_real_publication_requires_location_and_contact(self):
        self.login()
        row = self.row()
        row["demo"] = False
        self.assertEqual(self.client.post("/api/quibar/admin/businesses", json=row, headers=self.csrf).status_code, 422)
        row.update(latitude=-37.68, longitude=-72.01, whatsapp="+56912345678")
        result = self.client.post("/api/quibar/admin/businesses", json=row, headers=self.csrf)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertNotEqual(result.json()["id"], row["id"])

    def test_tiles_tms_conversion_and_metrics(self):
        with closing(sqlite3.connect(os.environ["QUIBAR_TILES_PATH"])) as db, db:
            db.executescript("CREATE TABLE metadata (name TEXT,value TEXT); CREATE TABLE tiles (zoom_level INT,tile_column INT,tile_row INT,tile_data BLOB);")
            db.executemany("INSERT INTO metadata VALUES (?,?)", [("format", "png"), ("minzoom", "0"), ("maxzoom", "2")])
            db.execute("INSERT INTO tiles VALUES (1,0,1,?)", (b"png-test",))
        self.assertTrue(self.client.get("/api/quibar/map").json()["available"])
        self.assertEqual(self.client.get("/tiles/1/0/0").content, b"png-test")
        self.assertEqual(self.client.get("/tiles/20/0/0").status_code, 404)
        self.assertEqual(self.client.post("/api/quibar/metrics", json={"event": "QR_MOSTRADO", "business_id": "grano-nativo"}).status_code, 202)
        self.login()
        self.assertEqual(self.client.get("/api/quibar/admin/metrics").json()[0]["count"], 1)

    def test_map_import_is_atomic_and_refuses_accidental_replacement(self):
        from .maps import install_map
        source = Path(self.tmp.name) / "source.mbtiles"
        with closing(sqlite3.connect(source)) as db, db:
            db.executescript("CREATE TABLE metadata (name TEXT,value TEXT); CREATE TABLE tiles (zoom_level INT,tile_column INT,tile_row INT,tile_data BLOB);")
            db.execute("INSERT INTO metadata VALUES ('format','png')")
            db.execute("INSERT INTO tiles VALUES (0,0,0,?)", (b"png-test",))
        result = install_map(source)
        self.assertEqual(result["tiles"], 1)
        with self.assertRaises(ValueError):
            install_map(source)
        self.assertEqual(self.client.get("/tiles/0/0/0").content, b"png-test")

    def test_spa_routes_and_unknown_api_paths_stay_separate(self):
        dist = Path(self.tmp.name) / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>Quibar SPA</html>")
        with patch.dict(os.environ, {"QUIBAR_DIST_DIR": str(dist)}):
            self.assertIn("Quibar SPA", self.client.get("/admin").text)
            self.assertEqual(self.client.get("/api/unknown").status_code, 404)
            self.assertEqual(self.client.get("/missing.js").status_code, 404)

    def test_user_deactivation_revokes_sessions_and_never_exposes_passwords(self):
        self.login()
        user_data = {"name": "Nuevo operador", "email": "new@example.test", "role": "Operador Territorial",
                     "active": True, "password": "a-long-test-password"}
        result = self.client.post("/api/quibar/admin/users", json=user_data, headers=self.csrf)
        self.assertEqual(result.status_code, 201, result.text)
        users = self.client.get("/api/quibar/admin/users").json()
        target = next(u for u in users if u["email"] == user_data["email"])
        self.assertNotIn("password", target)
        self.assertNotIn("password_hash", target)
        other = TestClient(app, client=("100.80.0.4", 1234), base_url="https://quibar.test")
        login = other.post("/api/quibar/admin/session", json={"email": user_data["email"], "password": user_data["password"]})
        self.assertEqual(login.status_code, 200)
        self.assertIn("Secure", login.headers["set-cookie"])
        self.assertIn("HttpOnly", login.headers["set-cookie"])
        self.assertEqual(other.get("/api/quibar/admin/session").status_code, 200)
        target.update(active=False, password="")
        result = self.client.put(f"/api/quibar/admin/users/{target['id']}", json=target, headers=self.csrf)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(other.get("/api/quibar/admin/session").status_code, 401)
        other.close()

    def test_search_index_tracks_moderation_and_edits(self):
        from .db import text_ranking
        self.login()
        row = self.row()
        row["keywords"] = "cafeteria especialprueba"
        self.client.put(f"/api/quibar/admin/businesses/{row['id']}", json=row, headers=self.csrf)
        self.assertIn(row["id"], text_ranking("especialprueba"))
        row["status"] = "Suspendido"
        self.client.put(f"/api/quibar/admin/businesses/{row['id']}", json=row, headers=self.csrf)
        self.assertNotIn(row["id"], text_ranking("especialprueba"))
        with sqlite3.connect(os.environ["QUIBAR_DB_PATH"]) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM registro_auditoria")
        db.close()


class LegacyMigration(unittest.TestCase):
    def test_legacy_records_keep_status_and_custom_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            records = json.loads((Path(__file__).parents[1] / "data/catalog.json").read_text())
            record = records[0]
            record["status"], record["hours"] = "Suspendido", "Horario editado antes de migrar"
            with closing(sqlite3.connect(path)) as db, db:
                keys = list(record)
                db.execute("CREATE TABLE businesses (" + ",".join(f'{key} TEXT' for key in keys) + ")")
                db.execute("INSERT INTO businesses VALUES (" + ",".join("?" for _ in keys) + ")",
                           [json.dumps(v) if isinstance(v, list) else int(v) if isinstance(v, bool) else v for v in record.values()])
            with patch.dict(os.environ, {"QUIBAR_DB_PATH": str(path)}):
                from .cli import main as cli
                backup = Path(directory) / "before.sqlite3"
                with patch("sys.argv", ["quibar", "backup", str(backup)]):
                    cli()
                with closing(sqlite3.connect(backup)) as saved:
                    names = {r[0] for r in saved.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    self.assertNotIn("alembic_version", names)
                    self.assertIn("businesses", names)
                initialize()
                self.assertEqual(approved(), [])
                with session() as db:
                    row = db.scalar(select(Comercio))
                    self.assertEqual(row.public_id, record["id"])
                    self.assertEqual(row.horario_atencion, record["hours"])
