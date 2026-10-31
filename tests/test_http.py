"""Loopback API tests using only the simulated device."""
import http.client,json,sys,tempfile,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Handler,ThreadingHTTPServer,Studio
from core import APP

class Loopback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=APP/'test-data';base.mkdir(exist_ok=True);cls.tmp=tempfile.TemporaryDirectory(dir=base)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.server.token='test-secret';cls.server.studio=Studio(Path(cls.tmp.name),True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.thread.join(3);cls.server.server_close();cls.tmp.cleanup()
    def request(self,path,headers=None,body=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        c.request('POST' if body else 'GET',path,body=json.dumps(body) if body else None,headers=headers or {})
        r=c.getresponse();result=(r.status,r.getheaders(),r.read());c.close();return result
    def test_token_origin_host_and_static_boundaries(self):
        self.assertEqual(self.request('/api/state')[0],403)
        auth={'X-Studio-Token':'test-secret'}
        code,headers,body=self.request('/api/state',auth);self.assertEqual(code,200);self.assertTrue(json.loads(body)['demo'])
        for override in ({'X-Studio-Token':'wrong'},{'Origin':'https://example.org'},{'Host':'evil.example'}):
            self.assertEqual(self.request('/api/state',{**auth,**override})[0],403)
        self.assertEqual(self.request('/../../app.py',auth)[0],404)
        self.assertEqual(self.request('/api/action',{},dict(action='read'))[0],403)
        self.assertEqual(self.request('/api/action',auth,dict(action='shutdown-camera'))[0],400)
        self.assertEqual(dict(headers)['X-Content-Type-Options'],'nosniff')
        self.assertNotIn(b'test-secret',body)
    def test_no_skip_install_confirmation(self):
        auth={'X-Studio-Token':'test-secret'}
        self.assertEqual(self.request('/api/action',auth,dict(action='install',payload=dict(token='fake',manual_ack=True)))[0],400)

if __name__=='__main__':unittest.main()
