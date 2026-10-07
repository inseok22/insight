import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('offline', ROOT / 'offline.py')
offline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(offline)


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.manifest = {'platform': 'linux/amd64', 'images': {key: f'example/{key}:1' for key in offline.SERVICES}}

    def render(self, host='10.2.3.4'):
        offline.render(self.folder, self.manifest, host, f'http://{host}:8000/metrics', offline.password_hash('test-only-password'))
        return json.loads((self.folder / 'compose.json').read_text())

    def test_reconfigure_keeps_credentials_and_volumes_changes_all_urls(self):
        first = self.render()
        creds = (self.folder / 'credentials.json').read_bytes()
        second = self.render('10.9.8.7')
        self.assertEqual(creds, (self.folder / 'credentials.json').read_bytes())
        self.assertEqual(first['volumes'], second['volumes'])
        self.assertEqual(second['services']['web']['ports'], ['10.9.8.7:8080:80'])
        text = (self.folder / 'backend.env').read_text()
        self.assertNotIn('10.2.3.4', text)
        self.assertEqual(text.count('var-gpu='), 8)
        self.assertNotIn('test-only-password', text)
        self.assertEqual((self.folder / 'credentials.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.folder / 'backend.env').stat().st_mode & 0o777, 0o600)

    def test_no_build_no_pull_and_no_public_db_or_exporter(self):
        compose = self.render()
        for name, service in compose['services'].items():
            self.assertEqual(service['pull_policy'], 'never')
            self.assertNotIn('build', service)
            if name in ('backend', 'mariadb', 'dcgm'):
                self.assertNotIn('ports', service)
        self.assertEqual(compose['services']['grafana']['environment']['GF_AUTH_ANONYMOUS_ENABLED'], 'false')
        # A real Compose parser validates JSON/YAML types, interpolation and env_file parsing.
        subprocess.run(['docker', 'compose', '-f', str(self.folder / 'compose.json'), 'config', '--quiet'], check=True)

    def test_invalid_configuration_does_not_write_partial_runtime(self):
        for host, url in [('10.0.0.1;touch /tmp/a', 'http://localhost/metrics'),
                          ('10.0.0.1', 'http://user:password@llm/metrics'),
                          ('10.0.0.1', 'http://llm/metrics?token=secret')]:
            with self.assertRaises(ValueError):
                offline.render(self.folder / 'new', self.manifest, host, url, 'hash')
            self.assertFalse((self.folder / 'new').exists())

    def test_manifest_rejects_unresolved_images_and_wrong_platform(self):
        with self.assertRaises(ValueError):
            offline.read_manifest(ROOT / 'images.example.json')
        self.manifest['platform'] = 'darwin/arm64'
        offline.write_json(self.folder / 'images.json', self.manifest)
        with self.assertRaises(ValueError):
            offline.read_manifest(self.folder / 'images.json')

    def test_tampered_bundle_and_incomplete_bundle_rejected(self):
        names = ['images.json', 'images.tar', 'offline.py', 'README.md']
        for name in names:
            (self.folder / name).write_text('test')
        offline.write_json(self.folder / 'SHA256.json', {n: offline.checksum(self.folder / n) for n in names})
        offline.verify_bundle(self.folder)
        (self.folder / 'images.tar').write_text('changed')
        with self.assertRaises(ValueError):
            offline.verify_bundle(self.folder)

    def test_metrics_check_rejects_empty_or_down_endpoints(self):
        for rows in ([], [{'value': [1, '0']}], [{'value': [1, 'NaN']}]):
            with patch.object(offline, 'query', return_value=rows):
                self.assertFalse(offline.collected(['up']))
        with patch.object(offline, 'query', return_value=[{'value': [1, '1']}]):
            self.assertTrue(offline.collected(['up']))


if __name__ == '__main__':
    unittest.main()
