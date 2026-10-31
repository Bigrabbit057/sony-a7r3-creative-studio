"""Narrow USB adapter. Importing this module never connects to a device.

All camera commands are constructed from constants, numeric IDs, random owned
paths and validated ASCII slot names. No terminal endpoint is exposed to UI.
"""
import copy,hashlib,io,json,os,re,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from core import APP,ASSETS,SCOPE,P,R,BRIDGE,SCRIPT,TOKEN,BASES,STYLES,digest,load,parse_seed,parse_record,choose_record,record_bytes
from storage import atomic_json
from transaction import read_values,guarded_transition
import payload
SIZES=load(ASSETS/'property-sizes.json')
EXPECTED={k:'00'*n for k,n in SIZES.items()}
def require(test,message):
    if not test:raise RuntimeError(message)
def lines(raw):return raw.replace(b'\r',b'').splitlines()
def mapped(name):return BRIDGE if name=='bridge.sh' else P+'/'+name

class Terminal:
    def __init__(self,camera,backend,path):self.camera=camera;self.backend=backend;self.path=path;self.sequence=0;self.enabled=False
    def receive(self,seconds=12,marker=None):
        raw=bytearray();end=time.monotonic()+seconds
        while time.monotonic()<end and len(raw)<131072:
            raw.extend(self.camera.dev.readTerminal());normalized=b'\n'+bytes(raw).replace(b'\r',b'')
            if marker:
                needle=('\n'+marker+'\n').encode()
                if needle in normalized and b'/usr/share/app # ' in normalized.split(needle,1)[1]:return bytes(raw)
            elif raw.endswith(b'/usr/share/app # '):return bytes(raw)
            time.sleep(.01)
        if marker:raise RuntimeError('终端未确认完成；停止操作，不能假定命令没有执行')
        return bytes(raw)
    def open(self):
        self.receive(1);self.camera.setTerminalEnable(False)
        self.camera.setTerminalEnable(True);self.enabled=True
        require(b'built-in shell (ash)' in self.receive(4),'相机终端身份不符')
        self.mounts()
    def close(self):
        if self.enabled:self.camera.setTerminalEnable(False);self.enabled=False
    def command(self,label,command,expected=None,timeout=12):
        self.sequence+=1;marker='CSSTUDIO_END_'+str(self.sequence)
        require(len(command)<850 and '\n' not in command and command.isascii(),'非法内部命令')
        self.camera.dev.writeTerminal((command+'; echo '+marker+'\n').encode('ascii'))
        raw=self.receive(timeout,marker);(self.path/(str(self.sequence)+'-'+label+'.bin')).write_bytes(raw)
        if expected:require(expected.encode() in lines(raw),'相机核对失败：'+label)
        return raw
    def mounts(self,mode='ro'):
        raw=self.command('mounts','cat /proc/self/mountinfo');rows=[]
        for line in lines(raw):
            p=line.decode('ascii',errors='replace').split()
            if len(p)<10 or not p[0].isdigit() or '-' not in p:continue
            i=p.index('-');rows.append(dict(target=p[4],options=p[5].split(','),source=p[i+2],fs=p[i+1],super=p[i+3].split(',')))
        u=[x for x in rows if x['target']=='/usr'];s=[x for x in rows if x['target']=='/setting'];r=[x for x in rows if x['target']=='/tmp_bt']
        require(len(u)==len(s)==len(r)==1,'挂载点不唯一')
        require(u[0]['source']=='/dev/nflasha15' and u[0]['fs']=='ext2' and mode in u[0]['options'] and mode in u[0]['super'] and 'relatime' in u[0]['options'],'/usr 挂载不匹配')
        require(s[0]['source']=='/dev/nflasha2' and s[0]['fs']=='vfat' and 'rw' in s[0]['options'],'/setting 不匹配')
        require(r[0]['fs']=='tmpfs' and 'rw' in r[0]['options'],'RAM 挂载不匹配')
        require(not any(x['target']==SCRIPT for x in rows),'存在未知启动文件覆盖')
        return rows
    def exists(self,path):
        raw=self.command('exists',f'if [ -e {path} ] || [ -L {path} ]; then echo CS_EXISTS; fi')
        return b'CS_EXISTS' in lines(raw)
    def regular(self,path):self.command('regular',f'[ -f {path} ] && [ ! -L {path} ] && echo CS_REGULAR','CS_REGULAR')
    def read(self,path):
        self.regular(path);out=io.BytesIO();self.backend.readFile(path,out);return out.getvalue()
    def put(self,path,data):
        require(not self.exists(path),'目标已存在：'+path);require(len(data)%512!=0,'USB 长度边界')
        self.backend.writeFile(path,io.BytesIO(data));require(self.read(path)==data,'上传读回不符：'+path)
    def replace(self,path,expected,data):
        require(self.read(path)==expected,'替换原值不符：'+path)
        self.put(path+'.next',data)
        self.command('replace',f'/bin/busybox mv {path}.next {path} && /bin/busybox sync && echo CS_REPLACED','CS_REPLACED')
        require(self.read(path)==data,'替换读回不符')
    def delete(self,path,expected):
        require(self.read(path)==expected,'删除原值不符');self.camera.deleteFile(path);require(not self.exists(path),'删除未确认')
    def mkdir(self,path):
        require(not self.exists(path),'目录已存在')
        self.command('mkdir',f'/bin/busybox mkdir -m 700 {path} && echo CS_CREATED','CS_CREATED')
    def boot_id(self):
        rows=[x for x in lines(self.command('boot-id','cat /proc/sys/kernel/random/boot_id')) if re.fullmatch(rb'[a-f0-9-]{36}',x)]
        require(len(rows)==1,'无法确认启动身份');return rows[0].decode()
    def ticks(self,pid):
        require(type(pid)==int and 1<pid<65536,'非法进程号')
        raw=self.command('process',f'if [ -f /proc/{pid}/stat ]; then cat /proc/{pid}/stat; fi')
        found=[x for x in lines(raw) if x.startswith(str(pid).encode()+b' (')]
        return int(found[0].split(b') ',1)[1].split()[19]) if len(found)==1 else None
    def pid(self,path):
        raw=self.read(path).strip();require(bool(re.fullmatch(rb'[1-9][0-9]{0,4}',raw)),'进程文件无效');return int(raw)
    def md5(self,path):
        self.regular(path);raw=self.command('hash',f'/bin/busybox md5sum {path}',timeout=30)
        found=re.findall(rb'^([0-9a-f]{32})\s+'+re.escape(path.encode())+rb'\s*$',raw.replace(b'\r',b''),re.M)
        require(len(found)==1,'无法核对文件哈希：'+path);return found[0].decode()
    def hardware(self):
        for name,md5 in [('/usr/lib/viewUnified2.so','642ec1fe93e49f02fe19f4455bd429b8'),('/usr/share/app/string_simplifiedchinese.uxc','a93646cb3495574c92ccc31be6b83544'),('/usr/bin/bk.elf','906081a186bdd76caa4df7bf6b33f2eb')]:
            require(self.md5(name)==md5,'相机文件版本不匹配：'+name)
        require(self.ticks(158)==125,'原厂 UI 进程布局不匹配')
        # The camera file-control API returns empty data for procfs maps
        # (reported file size is zero). Read this bounded pseudo-file through
        # the terminal and keep its completed output in the operation journal.
        maps=self.command('ui-maps','cat /proc/158/maps').replace(b'\r',b'')
        # The hook/table resides only in viewUnified2. Language resources can
        # move after startup and are never addressed by the six-slot hook.
        for pattern in [rb'^151d6000-15a09000 r-xp 00000000 .* /usr/lib/viewUnified2\.so$',rb'^15a10000-15c1f000 rw-p 00832000 .* /usr/lib/viewUnified2\.so$']:
            require(re.search(pattern,maps,re.M) is not None,'内存映射不匹配，拒绝写入')
    def memory(self,address,before,after=None,any_data=False):
        body,source=payload.memory_helper(address,before,after);d='/tmp_bt/csstudio-mem-'+uuid.uuid4().hex;self.mkdir(d)
        (self.path/(d.split('-')[-1]+'.s')).write_text(source)
        self.put(d+'/run.elf',body)
        self.command('memory',f'/bin/busybox chmod 700 {d}/run.elf && {d}/run.elf >{d}/result.bin && echo CS_MEMORY_RETURNED','CS_MEMORY_RETURNED')
        raw=self.read(d+'/result.bin');(self.path/(d.split('-')[-1]+'.bin')).write_bytes(raw)
        result=payload.check_frame(raw,address,before,after,any_data)
        self.delete(d+'/run.elf',body);self.delete(d+'/result.bin',raw)
        self.command('memory-clean',f'/bin/busybox rmdir {d} && echo CS_CLEAN','CS_CLEAN');return result

class Device:
    def __init__(self,data,progress=lambda s:None):self.data=Path(data);self.progress=progress;self.data.mkdir(parents=True,exist_ok=True)
    def journal(self,label):
        path=self.data/'backups'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+label);path.mkdir(parents=True)
        def record(event,data):
            with (path/'journal.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),event=event,**data),ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        return path,record
    def session(self,fn):
        from locking import usb_lock
        with usb_lock():return self._session(fn)
    def _session(self,fn):
        sys.path.insert(0,str(APP/'vendor'))
        # PyInstaller's USB loader searches the bundle by default. This project
        # intentionally ships no system driver: resolve the separately installed
        # libusb-win32 DLL only when the user starts a real camera session.
        if os.name=='nt':
            from usb.backend import libusb0
            library=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/libusb0.dll'
            require(library.is_file(),'未安装 libusb-win32，请先按说明安装相机驱动')
            require(libusb0.get_backend(find_library=lambda name:str(library) if name=='libusb0' else None) is not None,'无法加载 libusb-win32 驱动接口')
        from pmca.commands.usb import senserShellCommand
        from pmca.platform.backend.senser import SenserPlatformBackend
        from pmca.platform.properties import PropertyInterface
        entered=False;result=None
        def callback(camera):
            nonlocal entered,result
            entered=True;b=SenserPlatformBackend(camera);b.start();p=PropertyInterface(b)
            ident=dict(model=p.getProp('modelName'),firmware=p.getProp('firmwareVersion'),region=p.getProp('backupRegion'))
            require(ident==SCOPE,'不支持的相机：'+json.dumps(ident,ensure_ascii=False))
            serial=p.getProp('serialNumber');require(bool(serial),'无法读取机身身份，拒绝写入')
            fingerprint=digest((json.dumps(ident,sort_keys=True)+'|'+str(serial)).encode())
            result=fn(camera,b,ident,fingerprint)
        for attempt in range(4):
            senserShellCommand(driverName='libusb',complete=callback)
            if entered:break
            if attempt<3:self.progress('等待 USB 重新连接…');time.sleep(3)
        require(entered,'未找到相机。请检查海量存储器模式、数据线和 libusb-win32 驱动。')
        return result
    def installed(self,t):
        original,armed=payload.original_script(t.read(SCRIPT))
        if not t.exists(P):
            require(not armed and not t.exists(BRIDGE),'发现孤立的启动入口，请人工检查')
            return 'stock',None,None
        if t.exists(P+'/studio.json'):
            meta=json.loads(t.read(P+'/studio.json'));require(meta.get('format')=='creative-studio-runtime-v1','未知组件描述')
            files,manifest,_=payload.build(meta['names'],revision=meta.get('runtime_revision','legacy-v1'));require(meta==manifest,'组件描述校验不符');kind='studio-v1'
        else:
            # Accept only a complete known pair; never a half-updated mixture.
            observed={n:t.read(P+'/'+n) for n in ('title.sh','boot.sh')}
            candidates=[(rev,payload.base_runtime(rev)) for rev in ('legacy-v1','resource-v2')]
            matched=[(rev,f) for rev,f in candidates if all(observed[n]==f[n] for n in observed)]
            require(len(matched)==1,'启动辅助脚本不是完整的已知版本')
            revision,files=matched[0];kind='legacy-v1' if revision=='legacy-v1' else 'legacy-resource-v2'
            manifest={'names':payload.NAMES,'runtime_revision':revision,'files':{n:{'sha256':digest(b)} for n,b in files.items()}}
        require(armed,'组件存在但持久入口未完成；需要人工检查')
        for name,body in files.items():require(t.read(mapped(name))==body,'组件发生未知变化：'+name)
        require(t.read(P+'/enabled')==TOKEN,'组件未启用；请先恢复或检查上次操作')
        return kind,files,manifest
    def seed(self,t):
        records={k:t.read(P+'/slots.'+k) for k in ('a','b')};seq,key,seed=choose_record(records)
        if t.exists(R+'/state.tsv'):
            live=t.read(R+'/state.tsv');parse_seed(live);require(seed==live,'手动白平衡还未保存，请稍等后重新读取')
        return seed,records,seq
    def snapshot(self,t,b,identity,fingerprint):
        t.hardware();kind,files,manifest=self.installed(t)
        a=read_values(b,EXPECTED);second=read_values(b,EXPECTED);require(a==second,'两次设置读取不同，请停止菜单操作后再试')
        if kind=='stock':seed=None;wbs=[dict(mode='auto',kelvin=5500,ab=0,gm=0) for _ in range(6)];names=['SLOT'+str(i+1) for i in range(6)]
        else:seed,_,_=self.seed(t);wbs=parse_seed(seed);names=manifest['names']
        reverse={v[0]:k for k,v in STYLES.items()};slots=[]
        for i in range(6):
            nums={key:int.from_bytes(bytes.fromhex(a[f'0x{base+i:08x}']),'little',signed=True) for key,base in BASES.items()}
            require(nums['style'] in reverse,'遇到未支持的槽位风格枚举')
            slots.append(dict(slot=i+1,name=names[i],style=reverse[nums['style']],contrast=nums['contrast'],saturation=nums['saturation'],sharpness=nums['sharpness'],wb=wbs[i],wb_known=kind!='stock'))
        return dict(identity=identity,fingerprint=fingerprint,boot_id=t.boot_id(),installation=kind,values=a,slots=slots,seed_hex=seed.hex() if seed else None,names=names)
    def read(self):
        path,record=self.journal('read');self.progress('读取身份、组件和六槽记忆；两遍核对设置…')
        def call(c,b,i,f):
            t=Terminal(c,b,path)
            try:t.open();result=self.snapshot(t,b,i,f);atomic_json(path/'snapshot.json',result);return result
            finally:t.close()
        result=self.session(call);record('service_exited',{});return result
    def pause(self,t,files):
        # Only graceful stop of the exact known owned programs. Never kill.
        require(t.read(R+'/run.sh')==files['learner.sh'],'运行程序不是已知版本')
        require(t.read(R+'/boot-id').decode().strip()==t.boot_id(),'运行程序属于另一启动')
        pids=[t.pid(R+'/'+n) for n in ('learner.pid','supervisor.pid')];ticks=[t.ticks(p) for p in pids]
        require(all(x is not None for x in ticks),'联动已异常退出，请先检查日志')
        t.delete(P+'/enabled',TOKEN);t.command('disable-sync','/bin/busybox sync && echo CS_DISABLED','CS_DISABLED')
        for _ in range(35):
            now=[t.ticks(p) for p in pids]
            if all(x is None for x in now):break
            require(all(x is None or x==old for x,old in zip(now,ticks)),'进程号已被复用，停止操作');time.sleep(1)
        else:raise RuntimeError('联动没有正常退出，保留现场，不强制终止')
        require(b'CSBOOT_DONE' in t.read(R+'/boot.log') and b'CS_DONE' in t.read(R+'/trace.txt'),'联动退出记录不完整')
    def park_ram(self,t):
        dest='/tmp_bt/csstudio-old-'+uuid.uuid4().hex
        require(not t.exists(dest),'归档目录冲突')
        t.command('park',f'/bin/busybox mv {R} {dest} && echo CS_PARKED','CS_PARKED');return dest
    def start(self,t):
        require(not t.exists(R),'旧的运行目录尚未归档')
        t.put(P+'/enabled',TOKEN);t.command('enable-sync','/bin/busybox sync && echo CS_ENABLED','CS_ENABLED')
        t.command('launch',f'/bin/ash {BRIDGE} </dev/null >/dev/null 2>&1 & echo CS_LAUNCH_SENT','CS_LAUNCH_SENT')
        for _ in range(18):
            time.sleep(2)
            if not t.exists(R+'/boot.log'):continue
            log=t.read(R+'/boot.log')
            require(not any(x in log for x in (b'CSBOOT_DONE',b'CSBOOT_TITLE_FAILED',b'CSBOOT_NO_VALID_MEMORY',b'CSBOOT_OTHER_FOLLOWER')),'启动拒绝；请保留日志')
            if b'CSBOOT_LEARNER_STARTED ' in log and t.exists(R+'/trace.txt') and b'CS_BOOT_RECIPE ' in t.read(R+'/trace.txt'):
                require(t.ticks(t.pid(R+'/learner.pid')) is not None,'联动已退出');return
        raise RuntimeError('未确认新联动就绪')
    def clean_parked(self,t,d):
        # Only bounded files from this just-stopped runtime; no recursive delete.
        require(bool(re.fullmatch(r'/tmp_bt/csstudio-old-[0-9a-f]{32}',d)),'非法归档路径')
        raw=t.command('old-list',f'for f in {d}/*; do if [ -f "$f" ] && [ ! -L "$f" ]; then echo CS_OLD=${{f##*/}}; else echo CS_UNKNOWN; fi; done')
        require(b'CS_UNKNOWN' not in lines(raw),'归档目录含未知对象')
        names=[x.split(b'=',1)[1].decode() for x in lines(raw) if x.startswith(b'CS_OLD=')]
        allowed={n for n in load(ASSETS/'legacy-manifest.json')['files'] if n.endswith('.elf')}|{'supervisor.pid','learner.pid','boot-id','boot.log','trace.txt','last.bin','record-body','record-new','state.tsv','run.sh','alias-before.bin','enabled','next.tsv','state.tsv.new','state.new'}
        if not set(names)<=allowed:return # retain unknown files rather than delete
        for n in names:
            body=t.read(d+'/'+n);(t.path/('prior-ram-'+n)).write_bytes(body);t.delete(d+'/'+n,body)
        t.command('old-clean',f'/bin/busybox rmdir {d} && echo CS_OLD_CLEAN','CS_OLD_CLEAN')
    def apply(self,plan):
        path,record=self.journal('apply');atomic_json(path/'plan.json',plan)
        self.progress('离线生成简称组件并验证保护条件…');newfiles,newmeta,proof=payload.build(plan['names']);atomic_json(path/'native-proof.json',proof)
        def call(c,b,i,f):
            t=Terminal(c,b,path);stage='preflight';oldfiles=None;parked=None;changed_files=[];table_changed=False
            try:
                t.open();current=self.snapshot(t,b,i,f)
                require(digest(current)==plan['binding'],'相机、启动状态或设置已改变，请重新读取和预览')
                _,oldfiles,oldmeta=self.installed(t)
                oldcode=payload.hook(current['names']);newcode=payload.hook(plan['names'])
                t.memory(payload.ENTRY,(ASSETS/'entry.bin').read_bytes());t.memory(payload.CAVE,oldcode)
                for n,raw in oldfiles.items():(path/('before-'+n)).write_bytes(raw)
                oldstudio=t.read(P+'/studio.json') if t.exists(P+'/studio.json') else None
                oldseed,oldrecords,seq=self.seed(t)
                for name,raw in oldrecords.items():(path/('before-slots.'+name)).write_bytes(raw)
                record('pause_intent',{});stage='pausing';self.pause(t,oldfiles);stage='paused'
                require(read_values(b,EXPECTED)==current['values'],'暂停后设置已改变')
                require(self.seed(t)[0]==oldseed,'暂停时发生新的手调记忆，请重新读取')
                parked=self.park_ram(t)
                self.progress('保存六槽和白平衡，写入后完整核对…')
                stage='settings'
                if plan['changes']:guarded_transition(b,i,current['values'],plan['changes'],record)
                stage='components'
                for n,data in newfiles.items():
                    if data!=oldfiles[n]:
                        changed_files.append((mapped(n),oldfiles[n],data));t.replace(mapped(n),oldfiles[n],data)
                newrec=record_bytes(bytes.fromhex(plan['seed_hex']),seq+1)
                for name in ('a','b'):
                    changed_files.append((P+'/slots.'+name,oldrecords[name],newrec));t.replace(P+'/slots.'+name,oldrecords[name],newrec)
                meta=(json.dumps(newmeta,sort_keys=True)+'\n').encode()
                changed_files.append((P+'/studio.json',oldstudio,meta))
                if oldstudio is None:t.put(P+'/studio.json',meta)
                else:t.replace(P+'/studio.json',oldstudio,meta)
                if oldcode!=newcode:
                    table_changed=True;t.memory(payload.CAVE+104,oldcode[104:],newcode[104:])
                t.memory(payload.CAVE,newcode)
                for n,data in newfiles.items():require(t.read(mapped(n))==data,'组件最终校验失败')
                t.command('final-sync','/bin/busybox sync && echo CS_SYNC','CS_SYNC')
                stage='starting';self.start(t);stage='started'
                require(self.seed(t)[0]==bytes.fromhex(plan['seed_hex']),'记忆读回不一致')
                for _ in range(2):require(read_values(b,EXPECTED)==plan['after'],'启动后设置核对失败')
                self.clean_parked(t,parked);stage='complete';record('verified',dict(menu_verified=False))
                atomic_json(self.data/'last-apply.json',dict(path=str(path),fingerprint=f))
            except Exception as exc:
                record('error',dict(stage=stage,error=repr(exc)))
                if stage in ('settings','components'):
                    # No new process has been started yet. Roll back only exact
                    # captured/desired states, leaving unexplained bytes alone.
                    try:
                        if table_changed:
                            actual=t.memory(payload.CAVE+104,newcode[104:],any_data=True)
                            require(actual in (oldcode[104:],newcode[104:]),'名称表未知，停止回退')
                            if actual!=oldcode[104:]:t.memory(payload.CAVE+104,newcode[104:],oldcode[104:])
                        for remote,old,new in reversed(changed_files):
                            if t.exists(remote):
                                actual=t.read(remote);require(actual in (old,new),'组件含未知值，停止回退')
                                if actual==new:
                                    if old is None:t.delete(remote,new)
                                    else:t.replace(remote,new,old)
                            elif old is not None:raise RuntimeError('原文件丢失')
                            if t.exists(remote+'.next'):t.delete(remote+'.next',new)
                        actual=read_values(b,EXPECTED)
                        require(all(actual[k] in (current['values'][k],plan['after'][k]) for k in EXPECTED),'设置出现未知值，停止回退')
                        undo={k:current['values'][k] for k in plan['changes'] if actual[k]!=current['values'][k]}
                        if undo:guarded_transition(b,i,actual,undo,record)
                        self.start(t);require(read_values(b,EXPECTED)==current['values'],'恢复后设置不同')
                        record('rollback_verified',{});raise RuntimeError('写入失败，原配方与联动已恢复；请重新读取。') from exc
                    except Exception as recovery:
                        record('recovery_result',dict(message=str(recovery)))
                        raise RuntimeError('操作未完成。'+str(recovery)+' 日志：'+str(path)) from exc
                raise RuntimeError('操作停止于 '+stage+'；不要重复点击写入，请保留相机连接检查。日志：'+str(path)) from exc
            finally:t.close()
        self.session(call);record('service_exited',{})
        return dict(saved=True,backup=str(path),message='六槽、简称和白平衡记忆已写入，两遍读回通过，会话已退出。请拔线后切换槽位验收；电脑端新版尚需实机确认。')
