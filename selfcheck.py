"""Offline packaged-application smoke check. Never enumerates USB devices."""
import hashlib,sys
from core import ASSETS,APP,library_default,validate_library,compatibility
import payload

def run():
    lib=validate_library(library_default())
    files,manifest,proof=payload.build(payload.NAMES)
    expected=(ASSETS/'resource-v2/boot.sh').read_bytes()
    assert files['boot.sh']==expected and manifest['runtime_revision']=='resource-v2', 'Runtime revision mismatch'
    for name in ('index.html','style.css','app.js'):assert (APP/'static'/name).is_file()
    sys.path.insert(0,str(APP/'vendor'))
    # Imports resolve packaged dependencies; no driver construction or calls.
    import pmca.commands.usb,usb.backend.libusb0
    assert not any(x in sys.modules for x in ('keystone','unicorn','native.persistent'))
    return dict(ok=True,recipes=len(lib['recipes']),writable=sum(compatibility(r)['writable'] for r in lib['recipes']),runtime_files=len(files),template_integrity=proof['template_integrity_checked'],usb_dependencies_imported=True,camera_accessed=False)
