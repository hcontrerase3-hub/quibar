"""Container data transfer never changes the source or replaces populated state."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from . import container_ops


class ContainerData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.source = self.root / 'native'
        self.source.mkdir()
        self.env = patch.dict(os.environ, {'QUIBAR_DB_PATH': str(self.state / 'quibar.sqlite3')})
        self.env.start()
        self.state_patch = patch.object(container_ops, 'STATE', self.state)
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_import_snapshots_wal_and_refuses_existing_volume(self):
        path = self.source / 'quibar.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE preserved (value TEXT)')
            db.execute("INSERT INTO preserved VALUES ('dato original')")
            db.commit()
            (self.source / 'media').mkdir()
            (self.source / 'media/photo.webp').write_bytes(b'photo')
            container_ops.import_data(self.source)
            with closing(sqlite3.connect(self.state / 'quibar.sqlite3')) as imported:
                self.assertEqual(imported.execute('SELECT value FROM preserved').fetchone()[0], 'dato original')
                self.assertEqual(imported.execute('SELECT version_num FROM alembic_version').fetchone()[0], '0003_territory')
            with closing(sqlite3.connect(self.state / 'pre-migration.sqlite3')) as before:
                self.assertFalse(before.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchall())
            self.assertEqual((self.state / 'media/photo.webp').read_bytes(), b'photo')
            with self.assertRaises(ValueError):
                container_ops.import_data(self.source)
            # Migration did not write to the original database.
            self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchall())

    def test_complete_archive_and_no_overwrite(self):
        from .db import initialize
        initialize()
        (self.state / 'media').mkdir()
        (self.state / 'media/photo.webp').write_bytes(b'photo')
        (self.state / 'map.mbtiles').write_bytes(b'map')
        target = self.root / 'backup.tar.gz'
        container_ops.backup(target)
        with tarfile.open(target) as archive:
            self.assertIn('quibar.sqlite3', archive.getnames())
            self.assertEqual(archive.extractfile('media/photo.webp').read(), b'photo')
            self.assertEqual(archive.extractfile('map.mbtiles').read(), b'map')
        with self.assertRaises(FileExistsError):
            container_ops.backup(target)

    def test_invalid_source_leaves_target_empty(self):
        (self.source / 'quibar.sqlite3').write_bytes(b'not sqlite')
        with self.assertRaises(sqlite3.DatabaseError):
            container_ops.import_data(self.source)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_first_admin_setup_is_interactive_and_idempotent(self):
        from .cli import main
        with patch('sys.argv', ['quibar', 'setup-admin']), \
                patch('builtins.input', side_effect=['first@example.test', 'First administrator']), \
                patch('getpass.getpass', return_value='a-long-test-password'):
            main()
        with patch('sys.argv', ['quibar', 'setup-admin']), patch('builtins.input') as prompt:
            main()
            prompt.assert_not_called()

    def test_remote_model_is_never_downloaded(self):
        with patch.dict(os.environ, {'QUIBAR_OLLAMA_MODE': 'remote', 'QUIBAR_MODEL_PULL': '1', 'OLLAMA_URL': 'http://private-server:11434'}), \
                patch('backend.container_ops.httpx.Client') as client, \
                patch('backend.preload.main', return_value=0), self.assertRaises(SystemExit) as result:
            container_ops.model()
        self.assertEqual(result.exception.code, 0)
        client.return_value.__enter__.return_value.stream.assert_not_called()
