"""Dispatch checks without Docker or real project data: python -m unittest discover -s ops/docker."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        repo = Path(__file__).resolve().parents[2]
        shutil.copy(repo / 'quibar', self.root)
        shutil.copy(repo / 'docker.env.example', self.root)
        self.binary = self.root / 'bin'
        self.binary.mkdir()
        docker = self.binary / 'docker'
        docker.write_text('#!/bin/bash\nprintf "%s " "$@" >> "$CALL_LOG"\nprintf "\\n" >> "$CALL_LOG"\n')
        docker.chmod(0o755)
        self.log = self.root / 'calls'
        self.env = {**os.environ, 'PATH': f'{self.binary}:{os.environ["PATH"]}', 'CALL_LOG': str(self.log)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_launcher(self, *args):
        return subprocess.run(['bash', str(self.root / 'quibar'), *args], env=self.env,
                              capture_output=True, text=True, check=True)

    def test_start_leaves_native_configuration_untouched(self):
        native = self.root / '.env'
        native.write_text('MY_SETTING=preserved\n')
        self.run_launcher('iniciar')
        self.assertEqual(native.read_text(), 'MY_SETTING=preserved\n')
        config = self.root / '.quibar/production.env'
        config.write_text(config.read_text() + '\nQUIBAR_MODEL=custom-model\n')
        self.run_launcher('iniciar')
        self.assertIn('custom-model', config.read_text())
        calls = self.log.read_text()
        self.assertIn('up -d --build --wait app nginx maintenance', calls)
        self.assertIn('up -d --force-recreate model-init', calls)
        self.assertFalse((self.root / '.quibar/quibar.lock').exists())

    def test_development_is_separate_and_stop_preserves_volumes(self):
        self.run_launcher('desarrollar')
        self.run_launcher('--dev', 'detener')
        calls = self.log.read_text()
        self.assertIn('--project-name quibar-dev', calls)
        self.assertIn('-f compose.dev.yaml', calls)
        self.assertIn('QUIBAR_PORT=8001', (self.root / '.quibar/development.env').read_text())
        self.assertNotIn('down', calls)
        self.assertNotIn('--volumes', calls)

    def test_existing_lock_blocks_mutation(self):
        lock = self.root / '.quibar/quibar.lock'
        lock.mkdir(parents=True)
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_launcher('iniciar')
        self.assertTrue(lock.exists())

    def test_remote_does_not_start_an_ollama_container(self):
        config = self.root / '.quibar/production.env'
        config.parent.mkdir()
        config.write_text('QUIBAR_OLLAMA_MODE=remote\nOLLAMA_URL=http://100.97.53.61:11434\nQUIBAR_MODEL=gemma4:e2b\n')
        self.run_launcher('iniciar')
        self.assertNotIn('up -d ollama', self.log.read_text())
