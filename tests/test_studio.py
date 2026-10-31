import copy,hashlib,importlib,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,payload
from core import *
from app import Studio,DemoDevice,selected
from transaction import guarded_transition

class Recipes(unittest.TestCase):
    def test_inventory_and_defaults(self):
        lib=validate_library(library_default());self.assertEqual(len(lib['recipes']),77)
        self.assertEqual(sum(compatibility(r)['writable'] for r in lib['recipes']),64)
        self.assertEqual([r['short'] for r in selected(lib)],['E100','REALA','C200','Gold 200','PROVIA','HP5'])
    def test_boundaries_and_names(self):
        r=selected(library_default())[0]
        for k,v in [('contrast',4),('saturation',True),('sharpness',-4),('short','过长中文'),('short','../bad'),('short','TOOLONG99'),('short','A;halt')]:
            with self.subTest(k=k,v=v),self.assertRaises(ValueError):validate_recipe({**r,k:v})
        for axis,val in [('ab',.25),('gm',.1),('gm',float('nan')),('ab',8)]:
            with self.assertRaises(ValueError):validate_recipe({**r,'wb':{**r['wb'],axis:val}})
    def test_fixed_kelvin_effect_rejected(self):
        d=DemoDevice('.',lambda s:None);rs=selected(library_default())
        for w in [{'mode':'kelvin','kelvin':5500,'ab':0,'gm':0}]:
            bad=copy.deepcopy(rs);bad[0]['wb']=w
            with self.assertRaises(ValueError):build_plan(d.read(),bad,1)
        bad=copy.deepcopy(rs);bad[0]['effect']=1
        with self.assertRaises(ValueError):build_plan(d.read(),bad,1)
    def test_signed_wb_all_grid(self):
        for a in range(-7000,7001,500):
            for c in range(-7000,7001,250):
                v=wb_values(dict(mode='auto',ab=a/1000,gm=-c/1000));signed=lambda k:int.from_bytes(bytes.fromhex(v[k]),'little',signed=True)
                self.assertEqual(signed(WB_CURRENT[0])*1000+signed(WB_CURRENT[2]),a)
                self.assertEqual(signed(WB_CURRENT[1])*1000+signed(WB_CURRENT[3]),c)
                self.assertEqual([v[k] for k in WB_CURRENT],[v[k] for k in WB_MEMORY])
    def test_records_corruption_and_latest(self):
        seed=seed_bytes(selected(library_default()));record=record_bytes(seed,23)
        self.assertEqual(parse_record(record),(23,seed));self.assertEqual(choose_record({'a':b'broken','b':record}),(23,'b',seed))
        other=selected(library_default());other[0]['wb']['ab']=-3
        with self.assertRaises(ValueError):choose_record({'a':record,'b':record_bytes(seed_bytes(other),23)})
        for offset in (0,12,len(record)-3):
            raw=bytearray(record);raw[offset]^=1
            with self.assertRaises(ValueError):parse_record(bytes(raw))
    def test_plan_never_confuses_saturation_with_effect(self):
        d=DemoDevice('.',lambda s:None);s=d.read();s['values']['0x01070187']='03'
        p=build_plan(s,selected(library_default()),2)
        self.assertNotIn('0x01070187',p['changes']);self.assertEqual(p['after']['0x01070187'],'03')
        allowed={f'0x{b+i:08x}' for b in BASES.values() for i in range(6)}|set(wb_values(selected(library_default())[0]['wb']))|{'0x0107031c','0x01070762'}
        self.assertTrue(set(p['changes'])<=allowed)
    def test_model_scope(self):
        s=DemoDevice('.',lambda s:None).read()
        for k,v in [('model','ILCE-7RM3A'),('firmware','3.11'),('region','EU')]:
            bad=copy.deepcopy(s);bad['identity'][k]=v
            with self.assertRaises(ValueError):build_plan(bad,selected(library_default()),1)

class FakeBackup:
    def __init__(self,values,fail_at=None,fail_sync=False):self.values=copy.deepcopy(values);self.fail_at=fail_at;self.fail_sync=fail_sync;self.writes=0
    def readBackup(self,k):return bytes.fromhex(self.values[f'0x{k:08x}'])
    def writeBackup(self,k,v):
        self.writes+=1
        if self.fail_at==self.writes:raise OSError('injected write fault')
        self.values[f'0x{k:08x}']=v.hex()
    def syncBackup(self):
        if self.fail_sync:self.fail_sync=False;raise OSError('injected sync fault')

class Transactions(unittest.TestCase):
    def test_partial_write_and_sync_restore_exact_settings(self):
        s=DemoDevice('.',lambda s:None).read();rs=selected(library_default());rs[0]['contrast']=-2;rs[1]['saturation']=2;rs[0]['wb']['ab']=-3
        p=build_plan(s,rs,1);before=s['values']
        for n in range(1,len(p['changes'])+1):
            b=FakeBackup(before,fail_at=n)
            with self.subTest(n=n),self.assertRaises(RuntimeError):guarded_transition(b,SCOPE,before,p['changes'],lambda *a:None)
            self.assertEqual(b.values,before)
        b=FakeBackup(before,fail_sync=True)
        with self.assertRaises(RuntimeError):guarded_transition(b,SCOPE,before,p['changes'],lambda *a:None)
        self.assertEqual(b.values,before)
    def test_stale_and_other_properties_no_write(self):
        s=DemoDevice('.',lambda s:None).read();before=s['values'];b=FakeBackup(before);b.values['0x01070187']='02'
        with self.assertRaises(RuntimeError):guarded_transition(b,SCOPE,before,{'0x01070762':'01'},lambda *a:None)
        self.assertEqual(b.writes,0)

class Controller(unittest.TestCase):
    def setUp(self):
        self.base=APP/'test-data';self.base.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=self.base);self.s=Studio(Path(self.tmp.name),True);self.s.snapshot=self.s.device.read()
    def tearDown(self):
        assert Path(self.tmp.name).resolve().is_relative_to(self.base.resolve())
        self.tmp.cleanup()
    def wait(self):
        for _ in range(200):
            if not self.s.busy:return
            time.sleep(.01)
        self.fail('job timeout')
    def test_roundtrip_and_single_use(self):
        r=copy.deepcopy(self.s.library['recipes'][0]);r['contrast']=-1;self.s.action('save',{'recipe':r})
        p=self.s.action('preview',{});self.s.action('apply',dict(token=p['token'],manual_ack=True));self.wait();self.assertFalse(self.s.error)
        with self.assertRaises(ValueError):self.s.action('apply',dict(token=p['token'],manual_ack=True))
    def test_requires_manual_effect_ack(self):
        p=self.s.action('preview',{})
        with self.assertRaises(ValueError):self.s.action('apply',dict(token=p['token']))
    def test_five_ordered_confirmations_and_expiry(self):
        self.s.device.stock();self.s.snapshot=self.s.device.read();p=self.s.action('preview',{'kind':'install'})
        with self.assertRaises(ValueError):self.s.action('install',dict(token=p['token'],manual_ack=True))
        with self.assertRaises(ValueError):self.s.action('confirm',dict(token=p['token'],accepted=True,step=4,phrase=CONFIRM_PHRASE))
        receipt=None
        for step in range(5):
            result=self.s.action('confirm',dict(token=p['token'],accepted=True,step=step,receipt=receipt,phrase=CONFIRM_PHRASE));receipt=result['receipt']
        with self.assertRaises(ValueError):self.s.action('confirm',dict(token=p['token'],accepted=True,step=4,receipt=receipt,phrase=CONFIRM_PHRASE))
        self.s.action('install',dict(token=p['token'],manual_ack=True,receipt=receipt));self.wait();self.assertFalse(self.s.error)
        self.s.snapshot=self.s.device.read();p=self.s.action('preview',{});self.s.plan['expires']=0
        with self.assertRaises(ValueError):self.s.action('apply',dict(token=p['token'],manual_ack=True))
    def test_capture_preserves_learned_wb(self):
        self.s.snapshot['slots'][0]['wb']['gm']=-1.25
        self.s.action('capture',{});r=selected(self.s.library)[0];self.assertEqual(r['wb']['gm'],-1.25)
    def test_source_injection_block(self):
        r=copy.deepcopy(self.s.library['recipes'][0]);r['source']='javascript:alert(1)'
        with self.assertRaises(ValueError):validate_recipe(r)

class Native(unittest.TestCase):
    def test_names_do_not_change_code_and_helpers_verify(self):
        names=['A','12345678','C200','Gold 200','PROVIA','HP5'];h=payload.hook(names)
        self.assertEqual(h[:104],(ASSETS/'hook.bin').read_bytes()[:104]);self.assertEqual(payload.names_from_hook(h),names)
        from native.memory import build as mem,verify as verify_mem
        from native.checker import checker,verify_checker
        files,manifest,proof=payload.build(names);self.assertTrue(proof['template_integrity_checked'])
        cases=[]
        for name,before,after in [('cave-installed',h,None),('stage',(ASSETS/'cave-file-original.bin').read_bytes(),h)]:
            b,s=mem(158,payload.CAVE,before,after);check,cs=checker(payload.CAVE,before,after)
            self.assertEqual(files[name+'.elf'],payload.padded(b));self.assertEqual(files['ok-'+name+'.elf'],check)
            self.assertEqual(proof['sources'][name+'.s'],s);self.assertEqual(proof['sources']['ok-'+name+'.s'],cs)
            cases+=verify_mem(b,158,payload.CAVE,before,after)+verify_checker(check,payload.CAVE,before,after)
        self.assertEqual(len(cases),36)
        self.assertTrue(all(len(v)%512 for v in files.values()))
        self.assertTrue(all(hashlib.md5(v).hexdigest().encode() in files['boot.sh'] for n,v in files.items() if n not in ('boot.sh','bridge.sh')))
    def test_startup_forward_reverse_faults(self):
        from native.persistent import build,emulate
        # Synthetic complete preimage: avoids distributing any Sony firmware.
        raw=bytearray(b'#'+b' '*1281+b'\n');raw[44:63]=b'    # echo "normal"'.ljust(19);raw[391:409]=b'    # echo "debug"'.ljust(18);raw=bytes(raw)
        with patch.object(payload,'SCRIPT_SHA',digest(raw)):
            bundle=payload.startup_bundle(raw);self.assertTrue(bundle['template_integrity_checked'])
            states,steps=payload.startup_states(raw);self.assertEqual(len(states),7)
            self.assertEqual(payload.original_script(states[-1]),(raw,True))
            for before,after,(at,n) in zip(states,states[1:],steps):self.assertEqual(before[:at],after[:at]);self.assertEqual(before[at+n:],after[at+n:])
            faults=('ok','gate_missing','gate_wrong_token','gate_wrong_fs','open_denied','wrong_fs','statfs_failed','stat_failed','bad_dev','bad_inode','bad_mode','bad_links','bad_uid','bad_gid','bad_size','changed_preimage','seek_failed','read_failed','short_read','write_failed','short_write','sync_failed','reread_failed','reread_corrupt','close_failed')
            cases=0
            for i,(at,n) in enumerate(steps):
                for reverse in (False,True):
                    a,b=(i+1,i) if reverse else (i,i+1);name=('undo-' if reverse else 'do-')+str(i)
                    blob,src,gate,token=build(states[a],states[b],at,n,bundle['run'])
                    self.assertEqual(bundle['helpers'][name],payload.padded(blob));self.assertEqual(bundle['sources'][name],src)
                    for fault in faults:emulate(bundle['helpers'][name],states[a],states[b],at,n,gate,token,fault);cases+=1
            blob,src,gate,token=build(states[0],states[1],44,1,bundle['run'],True)
            self.assertEqual(bundle['helpers']['check'],payload.padded(blob));self.assertEqual(bundle['sources']['check'],src)
            emulate(blob,states[0],states[1],44,1,gate,token,'ok',True);cases+=1
            self.assertEqual(cases,301)
    def test_memory_template_equivalence(self):
        from native.memory import build,verify
        for address,n in [(payload.ENTRY,4),(payload.CAVE,200),(payload.CAVE+104,96)]:
            a=bytes((i*31+17)%256 for i in range(n));b=bytes((i*11+7)%256 for i in range(n))
            for aft in (None,b):
                blob,src=payload.memory_helper(address,a,aft);assembled,expected=build(158,address,a,aft)
                self.assertEqual(blob,payload.padded(assembled));self.assertEqual(src,expected);verify(blob,158,address,a,aft)
    def test_checker_not_exit_code_only(self):
        import struct
        before=b'1234';good=struct.pack('<8i',3,12345,4,1,4,4,0,0)+before+b'abcd'
        self.assertEqual(payload.check_frame(good,12345,before,b'abcd'),before)
        wrong=bytearray(good);struct.pack_into('<i',wrong,16,3)
        with self.assertRaises(ValueError):payload.check_frame(bytes(wrong),12345,before,b'abcd')

if __name__=='__main__':unittest.main()
