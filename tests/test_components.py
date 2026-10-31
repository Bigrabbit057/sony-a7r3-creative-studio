"""Host-side update/rollback integration with in-memory camera files, no USB."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import device,payload
from core import *
from app import DemoDevice,selected
from test_studio import FakeBackup

class Terminal:
    current=None
    def __new__(cls,*args):return cls.current
    def __init__(self,*args):pass
    def open(self):pass
    def close(self):pass
    def exists(self,p):return p in self.files
    def read(self,p):
        if p not in self.files:raise FileNotFoundError(p)
        return self.files[p]
    def put(self,p,b):
        if p in self.files:raise RuntimeError('exists')
        self.files[p]=b
    def replace(self,p,old,new):
        if self.read(p)!=old:raise RuntimeError('preimage')
        self.files[p]=new;self.count+=1
        if self.count==self.fail:raise OSError('injected replacement failure after mutation')
    def delete(self,p,b):
        if self.read(p)!=b:raise RuntimeError('delete preimage')
        del self.files[p]
    def memory(self,address,before,after=None,any_data=False):
        actual=self.entry if address==payload.ENTRY else self.hook if address==payload.CAVE else self.hook[104:]
        if not any_data and actual!=before:raise RuntimeError('memory preimage')
        if after is not None:
            if address!=payload.CAVE+104:raise RuntimeError('unexpected code write')
            self.hook=self.hook[:104]+after
        return actual
    def command(self,*args,**kw):return b''

class FakeDevice(device.Device):
    def session(self,fn):return fn(None,self.backend,SCOPE,'demo-only')
    def snapshot(self,*args):return copy.deepcopy(self.snap)
    def installed(self,t):return 'legacy-v1',self.oldfiles,{'names':payload.NAMES}
    def pause(self,t,files):t.delete(P+'/enabled',TOKEN)
    def park_ram(self,t):return '/tmp_bt/csstudio-old-'+'0'*32
    def start(self,t):
        t.put(P+'/enabled',TOKEN)
        names=payload.names_from_hook(t.hook);files,meta,_=payload.build(names)
        for n,b in files.items():
            if t.read(device.mapped(n))!=b:raise RuntimeError('incomplete runtime')
        if t.exists(P+'/studio.json') and json.loads(t.read(P+'/studio.json'))!=meta:raise RuntimeError('metadata mismatch')
        self.started=True
    def seed(self,t):
        records={k:t.read(P+'/slots.'+k) for k in ('a','b')};seq,key,seed=choose_record(records);return seed,records,seq
    def clean_parked(self,*args):pass

class Integration(unittest.TestCase):
    def run_case(self,fail=None):
        base=APP/'test-data';base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            d=FakeDevice(tmp);d.started=False;d.snap=DemoDevice('.',lambda x:None).read();d.snap['installation']='legacy-v1'
            d.oldfiles,_,_=payload.build(payload.NAMES);d.backend=FakeBackup(d.snap['values'])
            rs=selected(library_default());rs[0].update(short='TEST100',saturation=1);rs[0]['wb']['gm']=-.5
            plan=build_plan(d.snap,rs,1)
            t=object.__new__(Terminal);t.files={device.mapped(n):b for n,b in d.oldfiles.items()};t.files[P+'/enabled']=TOKEN
            oldrec=record_bytes(bytes.fromhex(d.snap['seed_hex']),19)
            for k in ('a','b'):t.files[P+'/slots.'+k]=oldrec
            oldfiles=copy.deepcopy(t.files);t.count=0;t.fail=fail;t.hook=payload.hook(payload.NAMES);t.entry=(ASSETS/'entry.bin').read_bytes()
            Terminal.current=t
            with patch.object(device,'Terminal',Terminal):
                if fail:
                    with self.assertRaises(RuntimeError):d.apply(plan)
                    self.assertEqual(d.backend.values,d.snap['values']);self.assertEqual(t.hook,payload.hook(payload.NAMES));self.assertEqual(t.files,oldfiles)
                else:
                    result=d.apply(plan);self.assertTrue(result['saved']);self.assertEqual(d.backend.values,plan['after']);self.assertEqual(t.hook,payload.hook(plan['names']))
                    self.assertEqual(d.seed(t)[0],bytes.fromhex(plan['seed_hex']))
                    self.assertEqual(json.loads(t.read(P+'/studio.json'))['names'],plan['names'])
            self.assertTrue(d.started)
    def test_update_names_parameters_and_memory(self):self.run_case()
    def test_each_file_mutation_failure_restores_legacy(self):
        # Changed runtime files: stage, cave-installed, their two checkers,
        # boot hash manifest, and both memory records = seven mutations.
        for n in range(1,8):
            with self.subTest(failure=n):self.run_case(n)

if __name__=='__main__':unittest.main()
