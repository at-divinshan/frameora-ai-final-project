"""Filesystem-only deployment tests; no application, database or provider imports."""
import json
from pathlib import Path
import runpy
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'app/core/owner_generation_config.py'


class DeploymentBatchTests(unittest.TestCase):
    def run_config(self, packaged, shared=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module = root / 'backend/app/core/owner_generation_config.py'
            module.parent.mkdir(parents=True)
            module.write_text(SOURCE.read_text())
            if packaged is not None:
                (root / 'backend/owner-generation.config.json').write_text(json.dumps(packaged))
            if shared is not None:
                (root / 'owner-generation.config.json').write_text(json.dumps(shared))
            return runpy.run_path(str(module))['BATCH_SIZE']

    def test_backend_only_keeps_two(self):
        self.assertEqual(self.run_config({'studioOwnerBatchSize': 2}), 2)

    def test_missing_packaged_config_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            self.run_config(None)

    def test_missing_invalid_setting_fails(self):
        for value in ({}, {'studioOwnerBatchSize': True}, {'studioOwnerBatchSize': 4}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_config(value)

    def test_mismatched_copies_fail(self):
        with self.assertRaises(ValueError):
            self.run_config({'studioOwnerBatchSize': 2}, {'studioOwnerBatchSize': 8})

    def test_repository_copies_match_and_remain_two(self):
        backend = SOURCE.parents[2]
        self.assertEqual(json.loads((backend / 'owner-generation.config.json').read_text()),
                         json.loads((backend.parent / 'owner-generation.config.json').read_text()))
        self.assertEqual(runpy.run_path(str(SOURCE))['BATCH_SIZE'], 2)

    def test_start_configuration(self):
        config = json.loads((SOURCE.parents[2] / 'railway.json').read_text())
        self.assertEqual(config['build']['builder'], 'RAILPACK')
        self.assertIn('uvicorn app.main:app', config['deploy']['startCommand'])
        self.assertIn('${PORT:-8000}', config['deploy']['startCommand'])
