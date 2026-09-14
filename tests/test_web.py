import errno
import json
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

import test_core
from vervision import __version__, core, web


class WebTests(unittest.TestCase):
    def setUp(self):
        test_core.CoreTests.setUp(self)
        self.server = web.create_server('127.0.0.1', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        test_core.CoreTests.tearDown(self)

    def request(self, endpoint, method='GET', **query):
        url = self.url + endpoint + '?' + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_health_identifies_running_version(self):
        status, data = self.request('/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(data, {'service':'vervision', 'version':__version__, 'read_only':True})

    def test_browse_unregistered_project_without_overview_or_initializing(self):
        other = self.root / 'unregistered project'
        handoff = other / '.handoff'
        handoff.mkdir(parents=True)
        raw = handoff / 'planning.md'
        raw.write_text('# Planning\n\nReadable without frontmatter.', encoding='utf-8')
        registry_before = core.REGISTRY.read_bytes()
        status, data = self.request('/api/documents', project=str(other))
        self.assertEqual(status, 200)
        self.assertEqual(data['documents'][0]['path'], '.handoff/planning.md')
        status, doc = self.request('/api/document', project=str(handoff), path='.handoff/planning.md')
        self.assertEqual(status, 200)
        self.assertIn('Readable without frontmatter', doc['body'])
        self.assertFalse((handoff / 'overview.md').exists())
        self.assertEqual(core.REGISTRY.read_bytes(), registry_before)
        self.assertEqual(list(handoff.iterdir()), [raw])

    def test_list_includes_history_search_and_canonical_markdown(self):
        archive = self.root / '.handoff/archive'
        archive.mkdir(exist_ok=True)
        (archive / 'old.md').write_text('# Old\nArchived evidence', encoding='utf-8')
        (self.root / 'ZEN.md').write_text('# Zen\nCanonical only.', encoding='utf-8')
        status, result = self.request('/api/documents', project=str(self.root), q='Archived evidence')
        self.assertEqual(status, 200)
        self.assertEqual(len(result['documents']), 1)
        self.assertTrue(result['documents'][0]['archived'])
        self.assertNotIn('body', result['documents'][0])
        _, document = self.request('/api/document', project=str(self.root), path='.handoff/modules/../../ZEN.md')
        self.assertEqual(document['body'], '# Zen\nCanonical only.')

    def test_read_only_rejects_all_old_mutations_without_changing_files(self):
        original = {p: p.read_bytes() for p in (self.root / '.handoff').rglob('*.md')}
        for endpoint, method in [('/api/modules','POST'),('/api/modules/feature/verify','POST'),
                                 ('/api/modules/feature','DELETE'),('/api/import','POST'),
                                 ('/api/continuations','POST'),('/api/modules','PUT'),('/api/modules','PATCH')]:
            with self.subTest(endpoint=endpoint, method=method):
                status, data = self.request(endpoint, method, project=str(self.root))
                self.assertEqual(status, 405)
                self.assertIn('仅供阅读', data['error'])
        self.request('/api/document', project=str(self.root), path='.handoff/modules/feature.md')
        self.assertEqual(original, {p:p.read_bytes() for p in (self.root / '.handoff').rglob('*.md')})

    def test_file_reader_does_not_escape_project_or_read_non_markdown(self):
        for name in ('../outside.md', 'src/feature.py', str(Path.home() / 'outside.md')):
            status, _ = self.request('/api/document', project=str(self.root), path=name)
            self.assertEqual(status, 404)
        status, data = self.request('/api/documents', project=str(self.root / 'missing'))
        self.assertEqual(status, 404)
        self.assertIn('没有 .handoff', data['error'])

    def test_unknown_port_owner_is_not_reused(self):
        fallback = web.create_server('127.0.0.1', self.server.server_port)
        try:
            self.assertNotEqual(fallback.server_port, self.server.server_port)
        finally:
            fallback.server_close()

    def test_reserved_port_falls_back_but_other_errors_propagate(self):
        with patch.object(web, 'ReaderServer', side_effect=[OSError(errno.EACCES, 'reserved'), self.server]) as create:
            self.assertIs(web.create_server('127.0.0.1', 8765), self.server)
            self.assertEqual(create.call_args.args[0], ('127.0.0.1', 0))
        with patch.object(web, 'ReaderServer', side_effect=OSError(errno.EINVAL, 'invalid')) as create:
            with self.assertRaises(OSError):
                web.create_server('127.0.0.1', 8765)
            self.assertEqual(create.call_count, 1)


if __name__ == '__main__':
    unittest.main()
