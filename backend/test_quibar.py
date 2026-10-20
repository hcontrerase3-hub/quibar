"""Pruebas de aceptación del catálogo, el diálogo y el límite de confianza."""

from contextlib import closing
import os
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import approved, initialize
from backend.preload import main as preload_model
from backend.rag import retrieve


class QuibarAcceptance(unittest.TestCase):
    def setUp(self):
        self.model_patches = [patch("backend.app.MODEL", "qwen3:14b-q4_K_M"), patch("backend.preload.MODEL", "qwen3:14b-q4_K_M")]
        for item in self.model_patches:
            item.start()
        self.directory = tempfile.TemporaryDirectory()
        self.db_var = patch.dict(os.environ, {"QUIBAR_DB_PATH": f"{self.directory.name}/test.sqlite3"})
        self.db_var.start()
        initialize()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db_var.stop()
        self.directory.cleanup()
        for item in self.model_patches:
            item.stop()

    def ask(self, query, **extra):
        response = self.client.post("/api/quibar/chat", json={"query": query, **extra})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_five_known_and_five_unknown_without_model(self):
        known = [
            ("Quiero comer algo rico", "Gastronomía"),
            ("Busco dónde alojarme", "Alojamiento"),
            ("Ideas para pasear", "Turismo"),
            ("Un regalo hecho a mano", "Artesanía"),
            ("Un café en Quilaco", "Gastronomía"),
            ("Quiero tomar un café en Quilaco", "Gastronomía"),
        ]
        unknown = [
            "¿Conoces la cafetería El Copihue?",
            "¿Tienen pizza en Quilaco?",
            "¿Existe Hotel Estrella Austral?",
            "¿Tienen sushi en Santa Bárbara?",
            "Busco bicicletas eléctricas",
        ]
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   side_effect=httpx.ConnectError("Ollama apagado")):
            for query, category in known:
                with self.subTest(query=query):
                    result = self.ask(query)
                    self.assertEqual(result["mode"], "basico")
                    self.assertTrue(result["matches"])
                    self.assertTrue(all(m["category"] == category for m in result["matches"]))
            for query in unknown:
                with self.subTest(query=query):
                    result = self.ask(query)
                    self.assertEqual(result["matches"], [])
                    self.assertIn("No cuento con ese registro", result["reply"])

    def test_model_choice_and_followup_use_catalog_facts(self):
        row = next(r for r in approved() if r["id"] == "rio-claro")
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   return_value=([row], "En el catálogo de ejemplo, Refugio Río Claro está en Quilaco.")):
            first = self.ask("¿Conoces Refugio Río Claro?")
        self.assertEqual(first["mode"], "ia_local")
        self.assertEqual(first["matches"][0]["id"], row["id"])
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   return_value=([row], f"Refugio Río Claro indica este horario: {row['hours']}.")):
            second = self.ask("¿Y su horario?", context_ids=[row["id"]],
                              history=[{"role": "user", "content": "¿Conoces Refugio Río Claro?"},
                                       {"role": "assistant", "content": first["reply"]}])
        self.assertIn(row["hours"], second["reply"])

    def test_natural_cafe_request_reaches_local_model(self):
        row = next(r for r in approved() if r["id"] == "grano-nativo")
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   return_value=([row], "En este catálogo de ejemplo, Grano Nativo ofrece Café, repostería en Quilaco.")) as choose:
            result = self.ask("Quiero tomar un café en Quilaco")
        choose.assert_awaited_once()
        self.assertEqual(result["mode"], "ia_local")
        self.assertEqual(result["matches"][0]["id"], "grano-nativo")
        self.assertIn("Café, repostería", result["reply"])
        self.assertNotIn("horario", result["reply"])

    def test_greeting_uses_model_without_inventing_a_business(self):
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   return_value=([], "¡Hola! Soy Quíbar. ¿Te gustaría descubrir un café o un paseo?")) as generate:
            response = self.ask("Hola")
        self.assertEqual(response["mode"], "ia_local")
        self.assertEqual(response["matches"], [])
        self.assertIn("¡Hola!", response["reply"])
        self.assertEqual(generate.await_args.args[1], [])
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   side_effect=httpx.ConnectError("Ollama apagado")):
            offline = self.ask("Hola")
        self.assertEqual(offline["mode"], "basico")
        self.assertIn("¡Hola!", offline["reply"])

    def test_greeting_protocol_generates_text_with_no_business_context(self):
        captured = []

        def greet_transport(request):
            payload = json.loads(request.content)
            captured.append(payload)
            return httpx.Response(200, json={"message": {"content": json.dumps({
                "reply": "¡Hola! Soy Quíbar. ¿Buscas un café o un paseo?"})}})

        real_client = httpx.AsyncClient
        with patch("backend.app.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(greet_transport), **kwargs)):
            result = self.ask("Hola")
        self.assertEqual(result["mode"], "ia_local")
        self.assertEqual(result["reply"], "¡Hola! Soy Quíbar. ¿Buscas un café o un paseo?")
        self.assertEqual(result["matches"], [])
        self.assertEqual(json.loads(captured[0]["messages"][1]["content"])["registros_aprobados"], [])
        self.assertNotIn("selected_ids", captured[0]["format"]["properties"])

    def test_fabricated_business_facts_are_rejected(self):
        row = next(r for r in approved() if r["id"] == "grano-nativo")
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   return_value=([row], "Grano Nativo cierra a las 23:45.")):
            result = self.ask("Un café en Quilaco")
        self.assertEqual(result["mode"], "basico")
        self.assertNotIn("23:45", result["reply"])
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   return_value=([], "¡Hola! Ve a Grano Nativo, abre a las 23:45.")):
            greeting = self.ask("Hola")
        self.assertEqual(greeting["mode"], "basico")
        self.assertNotIn("Grano Nativo", greeting["reply"])

    def test_unapproved_never_appears_or_becomes_context(self):
        with closing(sqlite3.connect(os.environ["QUIBAR_DB_PATH"])) as conn, conn:
            conn.execute("UPDATE comercio SET estado_moderacion = 'Suspendido' WHERE public_id = 'grano-nativo'")
        self.assertNotIn("grano-nativo", {r["id"] for r in self.client.get("/api/quibar/catalog").json()})
        self.assertEqual(retrieve("¿Conoces Grano Nativo?", approved()), [])
        result = self.ask("¿Y su horario?", context_ids=["grano-nativo"])
        self.assertEqual(result["matches"], [])

    def test_bad_model_response_falls_back_to_approved_facts(self):
        with patch("backend.app.generate_with_model", new_callable=AsyncMock,
                   side_effect=ValueError("ID inventado")):
            result = self.ask("¿Dónde queda Refugio Río Claro?")
        self.assertEqual(result["mode"], "basico")
        self.assertIn("Sector rural de Quilaco", result["reply"])

    def test_real_ollama_protocol_whitelists_selected_ids(self):
        row = next(r for r in approved() if r["id"] == "grano-nativo")
        model_reply = httpx.Response(200, json={"message": {"content": json.dumps({
            "selected_ids": ["grano-nativo"],
            "reply": "Si te apetece café en Quilaco, en este catálogo de ejemplo está Grano Nativo."})}},
                                     request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"))
        captured = []

        def fake_transport(request):
            captured.append(json.loads(request.content))
            return model_reply

        real_client = httpx.AsyncClient
        with patch("backend.app.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(fake_transport), **kwargs)):
            result = self.ask("Un café en Quilaco")
        self.assertEqual(result["mode"], "ia_local")
        self.assertEqual(result["matches"][0]["id"], row["id"])
        self.assertIn("Si te apetece café", result["reply"])
        self.assertEqual(captured[0]["model"], "qwen3:14b-q4_K_M")
        self.assertEqual(captured[0]["format"]["properties"]["selected_ids"]["items"]["enum"], [row["id"]])
        self.assertFalse(captured[0]["think"])

        forged = httpx.Response(200, json={"message": {"content": json.dumps({
            "selected_ids": ["negocio-inventado"], "reply": "Aquí hay un negocio inventado."})}},
                                request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"))
        with patch("backend.app.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(lambda request: forged), **kwargs)):
            result = self.ask("Un café en Quilaco")
        self.assertEqual(result["mode"], "basico")
        self.assertEqual(result["matches"][0]["id"], row["id"])

    def test_preload_uses_exact_local_model_and_reports_failure(self):
        calls = []
        real_client = httpx.Client

        def working_server(request):
            calls.append((request.url.path, request.content))
            if request.url.path.endswith("/tags"):
                return httpx.Response(200, json={"models": [{"name": "qwen3:14b-q4_K_M"}]})
            return httpx.Response(200, json={"done": True})

        with patch("backend.preload.httpx.Client", side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(working_server), **kwargs)):
            self.assertEqual(preload_model(), 0)
        payload = json.loads(calls[-1][1])
        self.assertEqual(payload["model"], "qwen3:14b-q4_K_M")
        self.assertEqual(payload["keep_alive"], "30m")

        def out_of_memory(request):
            if request.url.path.endswith("/tags"):
                return httpx.Response(200, json={"models": [{"name": "qwen3:14b-q4_K_M"}]})
            return httpx.Response(500, text="model requires more system memory")

        with patch("backend.preload.httpx.Client", side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(out_of_memory), **kwargs)):
            self.assertEqual(preload_model(), 1)


if __name__ == "__main__":
    unittest.main()
