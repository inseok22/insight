"""The image entry point must actually pass BACKEND_PORT to the HTTP server."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.serve import main


class ServerPortTest(unittest.TestCase):
    def tearDown(self):
        get_settings.cache_clear()

    def test_env_port_controls_uvicorn(self):
        for port in (18000, 18081):
            with self.subTest(port=port), patch.dict(os.environ, {'BACKEND_PORT': str(port)}), \
                 patch('app.serve.uvicorn.run') as run:
                get_settings.cache_clear()
                main()
                run.assert_called_once_with('app.main:app', host='0.0.0.0', port=port, workers=1)

    def test_local_dotenv_port_and_default(self):
        with patch.dict(os.environ, {}, clear=True), TemporaryDirectory() as directory:
            self.assertEqual(Settings(_env_file=None).backend_port, 18000)
            env = Path(directory) / '.env'
            env.write_text('BACKEND_PORT=18082\n')
            self.assertEqual(Settings(_env_file=env).backend_port, 18082)

    def test_invalid_ports_fail_before_listening(self):
        for port in ('', 'invalid', '0', '-1', '65536', '18000.5'):
            with self.subTest(port=port), patch.dict(os.environ, {'BACKEND_PORT': port}), \
                 patch('app.serve.uvicorn.run') as run:
                get_settings.cache_clear()
                with self.assertRaises(ValidationError):
                    main()
                run.assert_not_called()
