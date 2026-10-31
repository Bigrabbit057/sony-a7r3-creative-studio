"""Never enumerate USB or collect system drivers while building this app."""
hiddenimports=['glob','usb.backend.libusb0','usb.backend.libusb1']
binaries=[]
datas=[]
