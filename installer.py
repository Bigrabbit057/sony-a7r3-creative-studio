"""Explicit experimental installation. No raw-device writes, no reboot commands.

Only the exact tested ext2 file identity/content may be edited. Full /usr reads
are per device, twice; they do not establish an independent rescue channel.
"""
import hashlib,json,re,shutil,time,uuid
from pathlib import Path
from core import ASSETS,P,R,BRIDGE,SCRIPT,TOKEN,build_plan,record_bytes,digest
from device import Terminal,require,lines,mapped,EXPECTED
from transaction import read_values,guarded_transition
from storage import atomic_json
from packet import read_staged_file
from ext2 import inspect_ext2
import payload
PARTITION_SIZE=314572800

def full_backup(t,camera,path,progress):
    require(shutil.disk_usage(path).free>PARTITION_SIZE*3,'电脑空间不足，需要至少约 900MB 可用空间')
    d='/tmp_bt/csboot-full-'+uuid.uuid4().hex;t.mkdir(d);chunk=d+'/chunk.bin';hashes=[];image=path/'usr-original.bin'
    try:
        for pass_no in (1,2):
            h=hashlib.sha256()
            with (image.open('xb') if pass_no==1 else image.open('rb')) as f:
                for offset in range(0,PARTITION_SIZE,262144):
                    size=min(262144,PARTITION_SIZE-offset)
                    # Deleting our previous exact chunk avoids old tail bytes if
                    # this BusyBox dd implementation doesn't truncate output.
                    if offset or pass_no==2:
                        t.command('chunk-delete',f'/bin/busybox rm {chunk} && echo CS_CHUNK_REMOVED','CS_CHUNK_REMOVED')
                    raw=t.command('backup-chunk',f'/bin/busybox dd if=/dev/nflasha15 of={chunk} bs=512 skip={offset//512} count={size//512} 2>/dev/null && echo X >>{chunk} && /bin/busybox md5sum {chunk}',timeout=30)
                    md=re.findall(rb'^([0-9a-f]{32})\s+'+re.escape(chunk.encode())+rb'\s*$',raw.replace(b'\r',b''),re.M)
                    body,frame=read_staged_file(camera,chunk,size+2)
                    require(len(md)==1 and hashlib.md5(body).hexdigest().encode()==md[0] and body.endswith(b'X\n'),'分区读取校验失败')
                    block=body[:-2];h.update(block)
                    if pass_no==1:f.write(block)
                    else:require(f.read(size)==block,'两遍分区读取不一致，停止安装')
                    if offset%(262144*20)==0:progress(f'备份这台相机的 /usr：第 {pass_no}/2 遍，{(offset+size)*100//PARTITION_SIZE}%')
                if pass_no==1:f.flush();__import__('os').fsync(f.fileno())
            hashes.append(h.hexdigest())
        require(hashes[0]==hashes[1],'备份哈希不一致')
        with image.open('rb') as f:
            def read_at(at,n):f.seek(at);raw=f.read(n);require(len(raw)==n,'备份读取不完整');return raw
            fs,original=inspect_ext2(read_at,PARTITION_SIZE)
        target=fs['target']
        require(target['inode']==39074 and target['mode']=='0o100755' and target['uid']==57285 and target['gid']==1000 and target['links']==1 and target['blocks']==[163689,163690],'相机底层文件布局不同，不支持安装')
        atomic_json(path/'partition-backup.json',dict(complete=True,twice_identical=True,sha256=hashes[0],bytes=PARTITION_SIZE,filesystem=fs))
        return original,fs
    finally:
        # No guessed cleanup outside our unique staging directory.
        if t.exists(chunk):t.camera.deleteFile(chunk)
        t.command('backup-clean',f'/bin/busybox rmdir {d} && echo CS_BACKUP_CLEAN','CS_BACKUP_CLEAN')

def remount(t,mode):
    require(mode in ('ro','rw'),'非法挂载模式')
    t.command('remount-'+mode,f'/bin/busybox mount -n -t ext2 -o remount,{mode},relatime /dev/nflasha15 /usr; r=$?; echo CS_MOUNT_RC=$r','CS_MOUNT_RC=0')
    t.mounts(mode)

def edit_startup(t,bundle,reverse=False):
    d='/tmp_bt/csboot-install-'+bundle['run'];t.mkdir(d)
    for name,body in bundle['helpers'].items():
        (t.path/(name+'.s')).write_text(bundle['sources'][name]);t.put(d+'/'+name+'.elf',body)
        t.command('chmod',f'/bin/busybox chmod 700 {d}/{name}.elf && echo CS_EXEC','CS_EXEC')
    t.put(bundle['gate'],bundle['token']);attempted=False
    def step(i,back):
        a,b=(i+1,i) if back else (i,i+1);name=('undo-' if back else 'do-')+str(i)
        require(t.read(SCRIPT)==bundle['states'][a],'启动文件状态改变，未继续写入')
        t.command('startup-'+name,f'{d}/{name}.elf; r=$?; echo CS_EDIT_RC=$r','CS_EDIT_RC=0')
        require(t.read(SCRIPT)==bundle['states'][b],'启动文件读回不符')
    try:
        require(t.read(SCRIPT)==bundle['states'][6 if reverse else 0],'启动入口原值不符')
        if not reverse:t.command('native-precheck',f'{d}/check.elf; r=$?; echo CS_CHECK_RC=$r','CS_CHECK_RC=0')
        attempted=True;remount(t,'rw')
        for i in (range(5,-1,-1) if reverse else range(6)):step(i,reverse)
        t.command('startup-sync','/bin/busybox sync && echo CS_SYNC','CS_SYNC')
    except Exception:
        if attempted and not reverse:
            actual=t.read(SCRIPT)
            require(actual in bundle['states'],'发现未知的部分写入，已停止；不能保证回退')
            for i in range(bundle['states'].index(actual)-1,-1,-1):step(i,True)
        raise
    finally:
        if attempted:remount(t,'ro')
        if t.exists(bundle['gate']):t.delete(bundle['gate'],bundle['token'])
    # Keep native recovery helper copies on PC, remove exact RAM artifacts.
    for n,b in bundle['helpers'].items():t.delete(d+'/'+n+'.elf',b)
    t.command('startup-clean',f'/bin/busybox rmdir {d} && echo CS_PATCH_CLEAN','CS_PATCH_CLEAN')

def install(device,snapshot,recipes,active):
    require(snapshot['installation']=='stock','已有组件，请使用配方写入；不重复安装')
    plan=build_plan({**snapshot,'installation':'studio-v1'},recipes,active)
    files,manifest,proof=payload.build(plan['names']);path,record=device.journal('install')
    atomic_json(path/'preview.json',plan);atomic_json(path/'native-proof.json',proof)
    def call(c,b,i,f):
        t=Terminal(c,b,path);stage='preflight';created=[];bundle=None;started=False
        try:
            t.open();now=device.snapshot(t,b,i,f);require(now==snapshot,'预览后相机状态改变，停止安装')
            for name in (P,R,BRIDGE):require(not t.exists(name),'目标存在，拒绝覆盖')
            raw=t.command('other-runtime','for d in /tmp_bt/ppstudio-* /tmp_bt/pp-three-* /tmp_bt/creative-recipes-*; do if [ -f "$d/enabled" ]; then echo CS_OTHER; fi; done')
            require(b'CS_OTHER' not in lines(raw),'其他实验联动仍在运行')
            t.memory(payload.ENTRY,(ASSETS/'entry-original.bin').read_bytes());t.memory(payload.CAVE,(ASSETS/'cave-file-original.bin').read_bytes())
            original,fs=full_backup(t,c,path,device.progress);require(t.read(SCRIPT)==original,'备份期间启动文件改变')
            atomic_json(path/'device.json',dict(identity=i,fingerprint=f,boot_id=now['boot_id']))
            (path/'startBTCore.original').write_bytes(original)
            bundle=payload.startup_bundle(original);atomic_json(path/'startup-proof.json',dict(template_integrity_checked=bundle['template_integrity_checked'],run=bundle['run'],runtime_emulation=False))
            for n,body in bundle['helpers'].items():(path/(n+'.elf')).write_bytes(body)
            for n,src in bundle['sources'].items():(path/(n+'.s')).write_text(src)
            (path/'recovery-token.txt').write_bytes(bundle['token'])
            require(read_values(b,EXPECTED)==snapshot['values'],'备份后设置发生变化，未安装')
            stage='staging';t.mkdir(P)
            for n,data in files.items():created.append((mapped(n),data));t.put(mapped(n),data)
            meta=(json.dumps(manifest,sort_keys=True)+'\n').encode();created.append((P+'/studio.json',meta));t.put(P+'/studio.json',meta)
            rec=record_bytes(bytes.fromhex(plan['seed_hex']),1)
            for n in ('a','b'):created.append((P+'/slots.'+n,rec));t.put(P+'/slots.'+n,rec)
            for n in files:
                if n.endswith('.sh'):t.command('syntax',f'/bin/ash -n {mapped(n)} && echo CS_SYNTAX','CS_SYNTAX')
            stage='settings'
            if plan['changes']:guarded_transition(b,i,snapshot['values'],plan['changes'],record)
            stage='runtime';started=True;device.start(t)
            for _ in range(2):require(read_values(b,EXPECTED)==plan['after'],'联动启动后设置不符')
            stage='startup';device.progress('组件运行已核对，正在安装限定的启动入口…');edit_startup(t,bundle)
            require(t.read(SCRIPT)==bundle['states'][-1],'启动入口最终核对失败');t.mounts()
            for _ in range(2):require(read_values(b,EXPECTED)==plan['after'],'安装后设置不符')
            stage='complete';record('installed',dict(cold_boot_verified=False,menu_verified=False))
        except Exception as exc:
            record('install_error',dict(stage=stage,error=repr(exc)))
            # Restore only when all owned pieces remain exactly recognizable.
            # A startup partial-write failure stays explicit, never reported as
            # installed or recoverable just because a PC backup exists.
            try:
                if bundle and t.read(SCRIPT)==bundle['states'][-1]:edit_startup(t,bundle,reverse=True)
                require(digest(t.read(SCRIPT))==__import__('core').SCRIPT_SHA,'启动文件未恢复原厂，需人工处理')
                if started:
                    device.pause(t,files)
                    t.memory(payload.ENTRY,(ASSETS/'entry.bin').read_bytes(),(ASSETS/'entry-original.bin').read_bytes())
                    device.park_ram(t)
                actual=read_values(b,EXPECTED)
                require(all(actual[k] in (snapshot['values'][k],plan['after'][k]) for k in EXPECTED),'出现未知设置，拒绝自动回退')
                changes={k:snapshot['values'][k] for k in plan['changes'] if actual[k]!=snapshot['values'][k]}
                if changes:guarded_transition(b,i,actual,changes,record)
                for remote,data in reversed(created):
                    if t.exists(remote):t.delete(remote,data)
                if t.exists(P):t.command('remove-empty',f'/bin/busybox rmdir {P} && echo CS_EMPTY','CS_EMPTY')
                record('install_rollback_verified',{})
            except Exception as rollback:record('rollback_unconfirmed',dict(error=repr(rollback)))
            raise RuntimeError('安装没有完成，停止于 '+stage+'。请保留相机连接，查看恢复结果：'+str(path)) from exc
        finally:t.close()
    device.session(call);record('service_exited',{})
    return dict(installed=True,backup=str(path),message='安装和读回完成，服务已退出。尚未验证这台机身的断电启动；请按说明检查名称、白平衡及取电池重启。备份不保证救砖。')
