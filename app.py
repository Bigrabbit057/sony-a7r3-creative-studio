"""Loopback Creative Studio. --demo uses synthetic state and never imports USB."""
import argparse,copy,json,os,secrets,sys,threading,time,uuid,webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from core import *
from storage import atomic_json,read_json

def selected(library):
    byid={r['id']:r for r in library['recipes']};return [copy.deepcopy(byid[k]) for k in library['assignments']]

class DemoDevice:
    def __init__(self,data,progress):
        self.progress=progress;self.data=Path(data);lib=library_default();rs=selected(lib)
        self.snapshot=dict(identity=SCOPE.copy(),fingerprint='demo-only',boot_id='00000000-0000-0000-0000-000000000000',installation='studio-v1',values={k:'00'*n for k,n in load(ASSETS/'property-sizes.json').items()},seed_hex=seed_bytes(rs).hex(),names=[r['short'] for r in rs],slots=[])
        self.set_recipes(rs,1)
    def set_recipes(self,rs,active):
        s=self.snapshot;s['slots']=[dict(slot=i+1,name=r['short'],**{k:r[k] for k in ('style','contrast','saturation','sharpness','wb')},wb_known=True) for i,r in enumerate(rs)]
        s['names']=[r['short'] for r in rs];s['seed_hex']=seed_bytes(rs).hex()
        for i,r in enumerate(rs):
            for k,base in BASES.items():s['values'][f'0x{base+i:08x}']=(STYLES[r['style']][0] if k=='style' else r[k]).to_bytes(1,'little',signed=True).hex()
        s['values'].update(wb_values(rs[active-1]['wb']));s['values']['0x01070762']=f'{active-1:02x}';s['values']['0x0107031c']='00'
    def read(self):self.progress('演示：读取模拟相机，未访问 USB。');return copy.deepcopy(self.snapshot)
    def apply(self,plan):
        if digest(self.snapshot)!=plan['binding']:raise ValueError('模拟相机状态改变')
        self.set_recipes(plan['recipes'],plan['active']);return dict(saved=True,message='演示写入通过；没有连接或修改真实相机。')
    def stock(self):self.snapshot['installation']='stock';self.snapshot['seed_hex']=None

class Studio:
    def __init__(self,data,demo=False):
        self.data=Path(data);self.data.mkdir(parents=True,exist_ok=True);self.demo=demo;self.lock=threading.RLock()
        self.library=validate_library(read_json(self.data/'library.json',library_default()));self.save()
        self.busy=False;self.message='先浏览配方、分配六槽。连接操作由你点击开始。';self.error='';self.result=None;self.snapshot=None;self.plan=None;self.receipt=None;self.job=0
        if demo:self.device=DemoDevice(self.data,self.progress)
        else:
            from device import Device
            self.device=Device(self.data,self.progress)
    def save(self):atomic_json(self.data/'library.json',self.library)
    def progress(self,text):
        with self.lock:self.message=text
    def invalidate(self):self.plan=None;self.receipt=None
    def state(self):
        with self.lock:
            camera=None
            if self.snapshot:
                s=self.snapshot;camera={k:s[k] for k in ('identity','installation','slots','names')};camera['device_id']=s['fingerprint'][:12];camera['active']=int(s['values']['0x01070762'],16)+1
            return dict(demo=self.demo,busy=self.busy,message=self.message,error=self.error,result=self.result,job=self.job,library=self.library,schema=schema(),camera=camera,preview=self.public_plan())
    def public_plan(self):
        if not self.plan:return None
        p=self.plan;return dict(token=p['token'],kind=p['kind'],display=p['data']['display'],changes=len(p['data']['changes']),names=p['data']['names'],active=p['data']['active'],expires_in=max(0,int(p['expires']-time.monotonic())))
    def start_job(self,fn,on_done=None):
        self.busy=True;self.error='';self.result=None;self.job+=1;self.message='准备操作…'
        def run():
            try:
                result=fn()
                with self.lock:
                    if on_done:on_done(result)
                    self.result=result;self.message=result.get('message','操作完成，会话已退出。')
            except Exception as e:
                with self.lock:self.error=str(e);self.message='操作没有完成；请查看提示。'
                atomic_json(self.data/'last-error.json',dict(error=repr(e),utc=time.time()))
            finally:
                with self.lock:self.busy=False
        threading.Thread(target=run,daemon=True).start();return dict(job=self.job)
    def checked_plan(self,token,kind):
        if not self.plan or token!=self.plan['token'] or self.plan['kind']!=kind or self.plan['expires']<time.monotonic():raise ValueError('预览或确认已过期，请重新读取和预览')
        return self.plan
    def action(self,action,p):
        with self.lock:
            if self.busy:raise ValueError('操作进行中，请等会话退出后再继续')
            if action=='save':
                r=validate_recipe(p['recipe']);exists=any(x['id']==r['id'] for x in self.library['recipes'])
                if not exists and len(self.library['recipes'])>=500:raise ValueError('配方库最多 500 项')
                self.library['recipes']=[r if x['id']==r['id'] else x for x in self.library['recipes']] if exists else self.library['recipes']+[r]
                self.save();self.invalidate();return {'id':r['id']}
            if action=='assign':
                self.library=validate_library({**self.library,'assignments':p['assignments'],'active':p['active']});self.save();self.invalidate();return {'ok':True}
            if action=='import':
                new=validate_library(p['library']);self.library=new;self.save();self.invalidate();return {'imported':len(new['recipes'])}
            if action=='capture':
                if not self.snapshot or self.snapshot['installation']=='stock':raise ValueError('请先读取已安装组件的相机')
                rs=[];ids=[]
                for s in self.snapshot['slots']:
                    r=copy.deepcopy(self.library['recipes'][0]);r.update(id='camera-'+uuid.uuid4().hex,name=s['name']+' · 相机读取',short=s['name'],group='我的相机',source='',notes='从相机读取：含已学习的白平衡；曝光与 DRO 未读取，参考值设为 0 / 自动。',ev_thirds=0,dro='auto',effect=0,effect_sub=0)
                    r.update({k:s[k] for k in ('style','contrast','saturation','sharpness','wb')});rs.append(validate_recipe(r));ids.append(r['id'])
                self.library=validate_library({**self.library,'recipes':self.library['recipes']+rs,'assignments':ids,'active':min(6,max(1,int(self.snapshot['values']['0x01070762'],16)+1))});self.save();self.invalidate();return {'captured':6}
            if action=='read':
                self.invalidate();self.snapshot=None
                def read():
                    s=self.device.read();return dict(snapshot=s,message='读取完成，未修改配方。可预览写入或将当前六槽保存到配方库。')
                return self.start_job(read,lambda result:setattr(self,'snapshot',result.pop('snapshot')))
            if action=='preview':
                if self.snapshot is None:raise ValueError('先连接并读取相机')
                kind=p.get('kind','apply')
                if kind not in ('apply','install'):raise ValueError('未知操作')
                if kind=='install' and self.snapshot['installation']!='stock':raise ValueError('这台已安装组件，请使用日常写入')
                snap={**self.snapshot,'installation':'studio-v1'} if kind=='install' else self.snapshot
                data=build_plan(snap,selected(self.library),self.library['active'])
                self.plan=dict(token=secrets.token_hex(24),kind=kind,data=data,snapshot=copy.deepcopy(self.snapshot),expires=time.monotonic()+900)
                self.receipt=None;return self.public_plan()
            if action=='confirm':
                plan=self.checked_plan(p.get('token'),'install');step=integer(p.get('step'),0,4,'确认步骤')
                if p.get('accepted') is not True:raise ValueError('须明确确认当前风险')
                if self.receipt is None:
                    if step!=0:raise ValueError('请从第一项风险确认开始')
                    self.receipt=dict(token=secrets.token_hex(24),step=-1,plan=plan['token'])
                elif p.get('receipt')!=self.receipt['token']:raise ValueError('确认凭据失效')
                if step!=self.receipt['step']+1:raise ValueError('确认步骤顺序不符或重复')
                if step==4 and p.get('phrase')!=CONFIRM_PHRASE:raise ValueError('确认短语不完全一致')
                self.receipt['step']=step;return dict(receipt=self.receipt['token'],next=step+1)
            if action in ('apply','install'):
                plan=self.checked_plan(p.get('token'),action)
                if p.get('manual_ack') is not True:raise ValueError('请确认相机图片效果关闭，并了解曝光 / DRO 不自动联动')
                if action=='install' and (not self.receipt or self.receipt['step']!=4 or p.get('receipt')!=self.receipt['token'] or self.receipt['plan']!=plan['token']):raise ValueError('必须完成全部五项确认')
                data=copy.deepcopy(plan);self.invalidate();self.snapshot=None
                def work():
                    if action=='apply':return self.device.apply(data['data'])
                    if self.demo:
                        self.device.snapshot['installation']='studio-v1';self.device.set_recipes(data['data']['recipes'],data['data']['active']);return dict(installed=True,message='模拟安装完成，没有访问真实相机。')
                    from installer import install
                    return install(self.device,data['snapshot'],data['data']['recipes'],data['data']['active'])
                return self.start_job(work)
            if action=='demo-stock' and self.demo:self.device.stock();self.snapshot=None;self.invalidate();return {'ok':True}
            raise ValueError('未知操作')

class Handler(BaseHTTPRequestHandler):
    server_version='CreativeStudio/0.1'
    def log_message(self,*args):pass
    def send_json(self,status,value):self.send_bytes(status,json.dumps(value,ensure_ascii=False).encode(),'application/json; charset=utf-8')
    def send_bytes(self,status,body,mime):
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");self.end_headers();self.wfile.write(body)
    def host_ok(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def auth(self):
        return self.host_ok() and self.headers.get('X-Studio-Token')==self.server.token and self.headers.get('Origin',f'http://127.0.0.1:{self.server.server_port}')==f'http://127.0.0.1:{self.server.server_port}'
    def do_GET(self):
        path=urlsplit(self.path).path
        if not self.host_ok():return self.send_json(403,{'error':'拒绝外部主机'})
        if path in ('/api/state','/api/export'):
            if not self.auth():return self.send_json(403,{'error':'请从工具启动的页面进入'})
            return self.send_json(200,self.server.studio.state() if path=='/api/state' else self.server.studio.library)
        names={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if path not in names:return self.send_json(404,{'error':'未找到'})
        name,mime=names[path];self.send_bytes(200,(APP/'static'/name).read_bytes(),mime)
    def do_POST(self):
        if not self.auth():return self.send_json(403,{'error':'请求来源或令牌无效'})
        if urlsplit(self.path).path!='/api/action':return self.send_json(404,{'error':'未找到'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 1<=n<=2097152:raise ValueError('请求过大或为空')
            p=json.loads(self.rfile.read(n))
            if p.get('action')=='shutdown':
                with self.server.studio.lock:
                    if self.server.studio.busy:raise ValueError('相机会话还在进行，暂不能退出')
                    self.send_json(200,{'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
            result=self.server.studio.action(p['action'],p.get('payload',{}));self.send_json(200,result)
        except (ValueError,KeyError,TypeError) as e:self.send_json(400,{'error':str(e)})
        except Exception as e:self.send_json(500,{'error':str(e)})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--demo',action='store_true');ap.add_argument('--no-browser',action='store_true');ap.add_argument('--port',type=int,default=0);ap.add_argument('--data',type=Path);ap.add_argument('--self-check',type=Path,metavar='RESULT_JSON');args=ap.parse_args()
    if args.self_check:
        from selfcheck import run
        try:result=run()
        except Exception as e:atomic_json(args.self_check,dict(ok=False,error=repr(e),camera_accessed=False));raise
        atomic_json(args.self_check,result);return
    base=Path(os.environ.get('LOCALAPPDATA',str(APP)))/'A7R3-Creative-Studio';data=args.data or base/('demo' if args.demo else 'data')
    data.mkdir(parents=True,exist_ok=True)
    if sys.stdout is None:sys.stdout=(data/'console.log').open('a',encoding='utf-8',buffering=1)
    if sys.stderr is None:sys.stderr=sys.stdout
    # Hold an OS-owned byte lock for this data folder. Never trust a stale PID.
    lockfile=(data/'instance.lock').open('a+b');lockfile.seek(0);lockfile.write(b'1');lockfile.flush();lockfile.seek(0)
    if os.name=='nt':
        import msvcrt
        try:msvcrt.locking(lockfile.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            old=read_json(data/'server.json',{});url=old.get('url','')
            if re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/#token=[0-9a-f]{64}',url) and not args.no_browser:webbrowser.open(url)
            print('工具已运行。',flush=True);return
    studio=Studio(data,args.demo);server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);server.studio=studio;server.token=secrets.token_hex(32)
    url=f'http://127.0.0.1:{server.server_port}/#token={server.token}';atomic_json(data/'server.json',dict(url=url,pid=os.getpid(),demo=args.demo))
    print(url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    finally:server.server_close();lockfile.close()
if __name__=='__main__':main()
