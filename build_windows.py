"""Build the Windows folder application and a matching, private-data-free source archive."""
import hashlib,json,os,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    # Build in a fresh named output; never recursively remove a guessed path.
    out=ROOT/'dist'/'0.1.5'
    # Never let PyInstaller recursively replace an installed/running copy.
    # A release build requires a fresh, versioned destination.
    if out.exists():raise RuntimeError('版本输出目录已存在，请先核对并选择新的输出目录：'+str(out))
    out.mkdir(parents=True)
    cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--name','CreativeStudio','--distpath',str(out),'--workpath',str(ROOT/'build'),'--specpath',str(ROOT/'build'),'--paths',str(ROOT/'vendor'),'--exclude-module','native','--exclude-module','keystone','--exclude-module','unicorn','--exclude-module','elftools','--collect-all','certifi','--hidden-import','usb.backend.libusb0','--hidden-import','usb.backend.libusb1','--hidden-import','comtypes.automation','--add-data',str(ROOT/'assets')+os.pathsep+'assets','--add-data',str(ROOT/'static')+os.pathsep+'static',str(ROOT/'app.py')]
    cmd[3:3]=['--clean','--additional-hooks-dir',str(ROOT/'hooks')]
    # Defense in depth even if someone changes hook resolution later.
    os.environ['PYINSTALLER_USB_HOOK_SKIP_PYUSB_DISCOVERY']='1'
    subprocess.run(cmd,cwd=ROOT,check=True)
    target=out/'CreativeStudio'
    subprocess.run([sys.executable,str(ROOT/'collect_licenses.py')],cwd=ROOT,check=True)
    shutil.copytree(ROOT/'THIRD_PARTY_LICENSES',target/'THIRD_PARTY_LICENSES',dirs_exist_ok=True)
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md','RISK_NOTICE.md','TOMORROW.md','VERIFICATION.md','requirements.txt','requirements-dev.txt'):
        shutil.copyfile(ROOT/name,target/name)
    (target/'Demo.cmd').write_text('@echo off\r\nstart "" "%~dp0CreativeStudio.exe" --demo\r\n',encoding='ascii')
    # The source selection is an allowlist. Logs, full camera partitions,
    # personal manifests, recipes edited by the user, and venvs never enter it.
    roots=['assets','static','native','vendor','tests','hooks','THIRD_PARTY_LICENSES'];source=[]
    for p in ROOT.glob('*'):
        if p.is_file() and (p.suffix in ('.py','.md','.txt','.cmd') or p.name in ('LICENSE','.gitignore','.gitattributes')):source.append(p)
    for folder in roots:
        source += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')]
    sourcezip=target/'CreativeStudio-source.zip'
    with zipfile.ZipFile(sourcezip,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in sorted(source):z.write(p,'creative-studio/'+p.relative_to(ROOT).as_posix())
    sums={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
    (target/'SHA256SUMS.json').write_text(json.dumps(sums,indent=2)+'\n')
    zipout=out/'CreativeStudio-Windows-x64-0.1.5.zip'
    with zipfile.ZipFile(zipout,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in target.rglob('*'):
            if p.is_file():z.write(p,'CreativeStudio/'+p.relative_to(target).as_posix())
    print(json.dumps(dict(exe=str(target/'CreativeStudio.exe'),zip=str(zipout),bytes=zipout.stat().st_size,sha256=hashlib.sha256(zipout.read_bytes()).hexdigest(),source_files=len(source)),ensure_ascii=False))
if __name__=='__main__':main()
