"""Collect installed dependency license files for the source/binary bundle."""
import importlib.metadata as md,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEV={'keystone-engine','unicorn','pyelftools','pip'}

def main():
    target=ROOT/'THIRD_PARTY_LICENSES';target.mkdir(exist_ok=True);rows=[]
    for d in sorted(md.distributions(),key=lambda d:d.metadata['Name'].lower()):
        name=d.metadata['Name'];files=[]
        if name.lower() in DEV:continue
        for f in d.files or []:
            if any(k in Path(str(f)).name.lower() for k in ('license','copying','notice')) and str(f).lower().endswith(('.txt','.md','.rst','license','copying','notice','license.rst')):
                src=Path(d.locate_file(f))
                if not src.is_file() or src.stat().st_size>2000000:continue
                rel=name+'/'+str(f).replace('..','_').replace('\\','/');dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);files.append(rel)
        rows.append(dict(name=name,version=d.version,license=d.metadata.get('License-Expression') or d.metadata.get('License'),homepage=d.metadata.get('Home-page'),files=files))
    for name in ('LICENSE.txt','LICENSE'):
        src=Path(sys.base_prefix)/name
        if src.is_file():shutil.copyfile(src,target/'Python-LICENSE.txt');break
    # This dependency puts its LGPL notice in source headers, not wheel metadata.
    import axmlparserpy,usb,tlslite
    for package in (axmlparserpy,usb,tlslite):
        root=Path(package.__file__).parent
        for src in root.rglob('*.py'):
            dest=target/'library-sources'/root.name/src.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    lgpl=target/'setuptools/setuptools/_vendor/autocommand-2.2.2.dist-info/LICENSE'
    if lgpl.is_file():shutil.copyfile(lgpl,target/'LGPL-3.0.txt')
    (target/'dependencies.json').write_text(json.dumps(dict(python=sys.version,packages=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(packages=len(rows),license_files=sum(len(r['files']) for r in rows),source_header_license=['AxmlParserPY'],missing=[r['name'] for r in rows if not r['files'] and r['name']!='AxmlParserPY'])))
if __name__=='__main__':main()
