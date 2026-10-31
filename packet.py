import re,struct
HEADER=struct.Struct("<IHHBBBB")

def exact(driver,count):
    data=bytearray()
    empty_packets=0
    while len(data)<count:
        request=min(32768,count-len(data))
        part=driver.read(request)
        # A USB zero-length packet is a transfer boundary, not file EOF.
        # Never issue speculative padding reads; tolerate only bounded ZLPs
        # encountered while the declared payload is still incomplete.
        if not part:
            empty_packets+=1
            if empty_packets>16: raise ValueError('Too many empty USB packets before declared payload completed')
            continue
        if len(part)>request: raise ValueError('Oversized USB response')
        data.extend(part)
    return bytes(data)

def read_staged_file(camera,path,expected_size):
    assert re.fullmatch(r'/tmp_bt/csboot-full-[0-9a-f]{32}/chunk.bin',path)
    assert 514<=expected_size<=262146 and expected_size%512==2
    dev=camera.dev
    assert tuple(dev.driver.getId())==(0x054c,0x0336)
    name=path.encode('ascii')
    name+=b'\0'*(4-len(name)%4)
    request=struct.pack('<HH',2,len(name))+name
    sequence=dev._sequence
    dev.driver.write(HEADER.pack(len(request),0xff01,sequence,0,0,0,0)+request)
    raw=exact(dev.driver,HEADER.size)
    size,pfunc,seq,version,micon,offset,response=HEADER.unpack(raw)
    if (size,pfunc,seq,version,micon,offset,response)!=(expected_size,0xff01,sequence,3,0,0,1):
        raise ValueError('Unexpected staged-file response '+raw.hex())
    body=exact(dev.driver,size)
    dev._sequence+=1
    return body,dict(header_hex=raw.hex(),payload_bytes=len(body),extra_padding_read=False)
