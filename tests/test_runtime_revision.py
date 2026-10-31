"""Compatibility and rejection tests for the relocated language-resource fix."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import device
import payload
import app
from core import build_plan
from core import APP, ASSETS, P, SCRIPT, TOKEN


class Files:
    def __init__(self, runtime, meta=None):
        self.files = {device.mapped(n): b for n, b in runtime.items()}
        self.files[SCRIPT] = b'fixture-script'
        self.files[P + '/enabled'] = TOKEN
        if meta is not None: self.files[P + '/studio.json'] = json.dumps(meta).encode()
    def exists(self, path): return path == P or path in self.files
    def read(self, path): return self.files[path]


class Revisions(unittest.TestCase):
    def setUp(self):
        base = APP / 'test-data'; base.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.device = device.Device(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def installed(self, t):
        with patch.object(payload, 'original_script', return_value=(b'original', True)):
            return self.device.installed(t)
    def test_known_legacy_and_repaired_and_studio_revisions(self):
        for rev in ('legacy-v1', 'resource-v2'):
            base = payload.base_runtime(rev)
            kind, files, meta = self.installed(Files(base))
            self.assertEqual(files, base)
            self.assertEqual(kind, 'legacy-v1' if rev == 'legacy-v1' else 'legacy-resource-v2')
            generated, manifest, _ = payload.build(['TEST'] + payload.NAMES[1:], revision=rev)
            kind, files, meta = self.installed(Files(generated, manifest))
            self.assertEqual(kind, 'studio-v1'); self.assertEqual(meta, manifest)
    def test_mixed_or_damaged_runtime_is_refused(self):
        old = payload.base_runtime('legacy-v1'); new = payload.base_runtime()
        for name in ('title.sh', 'boot.sh'):
            mixed = dict(old); mixed[name] = new[name]
            with self.assertRaises(RuntimeError): self.installed(Files(mixed))
        t = Files(new); t.files[P + '/learner.sh'] += b'\n'
        with self.assertRaises(RuntimeError): self.installed(t)
    def test_new_recipe_does_not_downgrade_resource_fix(self):
        files, meta, _ = payload.build(['TEST'] + payload.NAMES[1:])
        self.assertEqual(meta['runtime_revision'], 'resource-v2')
        self.assertEqual(files['title.sh'], (ASSETS / 'resource-v2/title.sh').read_bytes())
        self.assertNotIn(b'run_title clear-original', files['title.sh'])
    def test_recognized_runtime_revisions_can_preview_daily_update(self):
        studio = app.Studio(self.tmp.name, demo=True)
        snapshot = studio.device.read()
        for kind in ('legacy-v1', 'legacy-resource-v2', 'studio-v1'):
            snapshot['installation'] = kind
            studio.snapshot = snapshot
            preview = studio.action('preview', {'kind': 'apply'})
            self.assertEqual(preview['kind'], 'apply')
            self.assertEqual(preview['changes'], 0)
        for kind in ('stock', 'unknown', 'legacy-resource-v3'):
            snapshot['installation'] = kind
            with self.assertRaises(ValueError):
                build_plan(snapshot, app.selected(studio.library), 1)
    def test_hardware_keeps_code_guards_without_language_address(self):
        t = object.__new__(device.Terminal)
        hashes = {'/usr/lib/viewUnified2.so': '642ec1fe93e49f02fe19f4455bd429b8',
                  '/usr/share/app/string_simplifiedchinese.uxc': 'a93646cb3495574c92ccc31be6b83544',
                  '/usr/bin/bk.elf': '906081a186bdd76caa4df7bf6b33f2eb'}
        t.md5 = lambda path: hashes[path]
        t.ticks = lambda pid: 125
        mappings = b'151d6000-15a09000 r-xp 00000000 fc:0f 1 /usr/lib/viewUnified2.so\n15a10000-15c1f000 rw-p 00832000 fc:0f 1 /usr/lib/viewUnified2.so\n0ed79000-0edcc000 r--p 00000000 fc:0f 2 /usr/share/app/string_simplifiedchinese.uxc\n'
        def no_file_control(path): raise AssertionError('procfs must not use file-control reads')
        t.read = no_file_control
        t.command = lambda *args: mappings
        t.hardware()
        t.command = lambda *args: mappings.replace(b'151d6000-', b'151d7000-')
        with self.assertRaises(RuntimeError): t.hardware()
        t.command = lambda *args: b''
        with self.assertRaises(RuntimeError): t.hardware()
        t.command = lambda *args: mappings
        hashes['/usr/lib/viewUnified2.so'] = '0' * 32
        with self.assertRaises(RuntimeError): t.hardware()

    def test_terminal_reopens_after_interrupted_session(self):
        calls = []
        camera = type('Camera', (), {'setTerminalEnable': lambda self, value: calls.append(value)})()
        t = device.Terminal(camera, None, Path(self.tmp.name))
        t.receive = lambda seconds, **kwargs: b'old prompt' if seconds == 1 else b'built-in shell (ash)'
        t.mounts = lambda: []
        t.open(); self.assertEqual(calls, [False, True])
        t.close(); self.assertEqual(calls, [False, True, False])


if __name__ == '__main__': unittest.main()
