"""Build only scoped, exact-preimage helpers. No USB or filesystem remounts."""
import copy,hashlib,re,struct,uuid
from core import ASSETS,P,R,SCRIPT_SHA,load,digest
BASE=0x151d6000;CAVE=BASE+0x832600;ENTRY=BASE+0x5a3480
PREFIX=104;WIDTH=16;NAMES=['E100','REALA','C200','Gold 200','PROVIA','HP5']
def padded(b):return b+b'\0\0' if len(b)%512==0 else b
def hook(names):
    if len(names)!=6:raise ValueError('需要六个名称')
    for n in names:
        if not isinstance(n,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9 +_-]{0,7}',n):raise ValueError('简称超出已验证范围')
    original=(ASSETS/'hook.bin').read_bytes()
    if len(original)!=200:raise ValueError('名称模板损坏')
    return original[:PREFIX]+b''.join(n.encode().ljust(WIDTH,b'\0') for n in names)
def names_from_hook(raw):
    if len(raw)!=200 or raw[:PREFIX]!=(ASSETS/'hook.bin').read_bytes()[:PREFIX]:raise ValueError('未知名称代码')
    out=[]
    for i in range(6):
        field=raw[PREFIX+i*WIDTH:PREFIX+(i+1)*WIDTH];n=field.split(b'\0')[0].decode('ascii')
        if field!=n.encode().ljust(WIDTH,b'\0'):raise ValueError('未知名称布局')
        out.append(n)
    if hook(out)!=raw:raise ValueError('名称数据不匹配')
    return out
def base_runtime(revision='resource-v2'):
    if revision not in ('legacy-v1','resource-v2'):raise ValueError('未知启动组件版本')
    legacy=load(ASSETS/'legacy-manifest.json')['files'];files={n:(ASSETS/'runtime'/n).read_bytes() for n in legacy}
    if any(digest(files[n])!=m['sha256'] for n,m in legacy.items()):raise ValueError('运行程序模板校验失败')
    if revision=='resource-v2':
        patch=load(ASSETS/'resource-v2/proof.json')
        if not patch['passed'] or set(patch['files'])!={'title.sh','boot.sh'}:raise ValueError('启动修订模板不完整')
        for n,m in patch['files'].items():
            b=(ASSETS/'resource-v2'/n).read_bytes()
            if digest(b)!=m['sha256']:raise ValueError('启动修订模板校验失败')
            files[n]=b
    return files
def build(names,verify=True,revision='resource-v2'):
    from templates import fill
    files=base_runtime(revision)
    code=hook(names);old=(ASSETS/'cave-file-original.bin').read_bytes();sources={}
    for name,before,after in [('cave-installed',code,None),('stage',old,code)]:
        values={'before':before}
        if after is not None:values['after']=after
        b,s=fill(f'mem-{CAVE:x}-{len(before)}-{int(after is not None)}',values);b=padded(b)
        check,cs=fill(f'check-{int(after is not None)}',values)
        files[name+'.elf']=b;files['ok-'+name+'.elf']=check;sources[name+'.s']=s;sources['ok-'+name+'.s']=cs
    boot=files['boot.sh'].decode()
    for n,b in files.items():
        if n in ('boot.sh','bridge.sh'):continue
        pattern=r'(check_file "\$P/'+re.escape(n)+r'" )[0-9a-f]{32}( \|\| exit 18)'
        boot,count=re.subn(pattern,lambda m:m[1]+hashlib.md5(b).hexdigest()+m[2],boot)
        if count!=1:raise ValueError('启动模板内容不符：'+n)
    files['boot.sh']=boot.encode()
    if len(files['boot.sh'])%512==0:files['boot.sh']+=b'\n# padding\n'
    if any(not b or len(b)%512==0 for b in files.values()):raise ValueError('USB 传输长度边界未处理')
    manifest=dict(format='creative-studio-runtime-v1',names=names,files={n:{'sha256':digest(b),'md5':hashlib.md5(b).hexdigest(),'bytes':len(b)} for n,b in files.items()})
    if revision!='legacy-v1':manifest['runtime_revision']=revision
    return files,manifest,dict(template_integrity_checked=True,sources=sources,camera_accessed=False)
def memory_helper(address,before,after=None):
    from templates import fill
    values={'before':before}
    if after is not None:values['after']=after
    b,s=fill(f'mem-{address:x}-{len(before)}-{int(after is not None)}',values)
    return padded(b),s
def check_frame(raw,address,before,after=None,any_data=False):
    n=len(before)
    if len(raw)!=32+2*n:raise ValueError('内存结果长度不符')
    fd,seek,nread,match,nwrite,nagain,closed,rollback=struct.unpack('<8i',raw[:32])
    if fd<0 or seek!=address or nread!=n or closed!=0:raise ValueError('内存读取失败')
    if not any_data and raw[32:32+n]!=before:raise ValueError('内存原值已改变')
    if after is not None and (match,nwrite,nagain,rollback,raw[32+n:])!=(1,n,n,0,after):raise ValueError('内存写入或核对失败')
    return raw[32:32+n]
def startup_states(original):
    if digest(original)!=SCRIPT_SHA or len(original)!=1283:raise ValueError('启动文件不是受支持的原厂版本')
    current=original;states=[current];steps=[]
    for phase in ('guard','staged','active'):
        for at,n in ((44,19),(391,18)):
            replacement=b'#' if phase=='guard' else b's' if phase=='active' else b'#h /setting/cs &'.ljust(n)
            after=current[:at]+replacement+current[at+len(replacement):]
            steps.append((at,len(replacement)));states.append(after);current=after
    return states,steps
def original_script(raw):
    if len(raw)!=1283:raise ValueError('启动文件长度不符')
    original=bytearray(raw)
    for at,n,text in ((44,19,b'    # echo "normal"'),(391,18,b'    # echo "debug"')):original[at:at+n]=text.ljust(n)
    original=bytes(original)
    states,_=startup_states(original)
    if raw not in (states[0],states[-1]):raise ValueError('启动文件含有未知或未完成的修改')
    return original,raw==states[-1]
def startup_bundle(original,verify=True):
    from templates import fill
    states,steps=startup_states(original);run=uuid.uuid4().hex;helpers={};sources={}
    gate='/tmp_bt/csboot-install-'+run+'/permit'
    token=('CSBOOT_PERSISTENT_MARKER_V1:'+run+'\n').encode()
    for i,(at,n) in enumerate(steps):
        for reverse in (False,True):
            a,b=(i+1,i) if reverse else (i,i+1);name=('undo-' if reverse else 'do-')+str(i)
            blob,src=fill(f'persist-{at}-{n}-0',{'before':states[a],'after':states[b],'run':run.encode()})
            helpers[name]=padded(blob);sources[name]=src
    blob,src=fill('persist-44-1-1',{'before':states[0],'after':states[1]})
    helpers['check']=padded(blob);sources['check']=src
    return dict(run=run,states=states,helpers=helpers,sources=sources,gate=gate,token=token,template_integrity_checked=True)
