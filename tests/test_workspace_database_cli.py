import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from apps.factory_lab.database_sources_cli import main


class DatabaseSourcesCLITest(unittest.TestCase):
    def invoke(self, *args):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(list(map(str, args))), 0)
        return json.loads(stdout.getvalue())

    def test_register_inspect_and_drift_keep_full_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, registry = root / 'private-source.sqlite', root / 'registry'
            with sqlite3.connect(source) as conn:
                conn.execute('create table records (id integer primary key, value text)')
                conn.executemany('insert into records values (?, ?)', [(i, str(i)) for i in range(1201)])
            registered = self.invoke('--registry', registry, 'register', source, '--label', 'Example')
            self.assertNotIn(str(root), json.dumps(registered))
            source_id = registered['source_id']
            catalog = self.invoke('--registry', registry, 'inspect', source_id, '--sample-limit', 2)
            self.assertEqual(catalog['tables'][0]['row_count'], 1201)
            self.assertEqual(len(catalog['tables'][0]['sample']), 2)
            with sqlite3.connect(source) as conn:
                conn.execute('insert into records values (1201, "new")')
            changed = self.invoke('--registry', registry, 'check-drift', source_id)
            self.assertEqual(changed['status'], 'changed')
            frozen = self.invoke('--registry', registry, 'inspect', source_id)
            self.assertEqual(frozen['tables'][0]['row_count'], 1201)

    def test_missing_registry_error_omits_private_path(self):
        with tempfile.TemporaryDirectory() as directory:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                main(['--registry', directory + '/secret-location', 'inspect', '0' * 32])
            self.assertEqual(raised.exception.code, 1)
            self.assertNotIn(directory, stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
