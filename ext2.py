import struct,hashlib
from core import SCRIPT_SHA as EXPECTED_SHA
def sha(data):return hashlib.sha256(data).hexdigest()

def inspect_ext2(read_at, partition_size):
    first = read_at(0, 4096)
    sb = first[1024:2048]
    u16 = lambda at: struct.unpack_from('<H', sb, at)[0]
    u32 = lambda at: struct.unpack_from('<I', sb, at)[0]
    assert sb[56:58] == b'\x53\xef', 'Not ext2'
    blocksize = 1024 << u32(24)
    blocks, firstdata, pergroup, ipg = u32(4), u32(20), u32(32), u32(40)
    inode_size = u16(88) if u32(76) else 128
    assert blocksize == 1024 and firstdata == 1 and inode_size == 128
    assert 0 < pergroup <= 8192 and 0 < ipg <= 8192
    assert 0 < blocks * blocksize <= partition_size <= 512 * 1024 * 1024
    assert u32(96) & ~2 == 0, 'Unsupported ext2 incompat features'
    groups = (blocks - firstdata + pergroup - 1) // pergroup
    assert 0 < groups <= 128
    table_size = (groups * 32 + 1023) // 1024 * 1024
    bgd = read_at(2048, table_size)
    used_groups, nodes, directories = {}, [], []

    def block(number):
        assert firstdata <= number < blocks
        return read_at(number * blocksize, blocksize)

    def inode(number):
        assert 1 <= number <= u32(0)
        group, index = divmod(number - 1, ipg)
        assert group < groups
        descriptor = bgd[group * 32:(group + 1) * 32]
        block_bitmap, inode_bitmap, inode_table = struct.unpack_from('<III', descriptor)
        for p in (block_bitmap, inode_bitmap, inode_table):
            assert firstdata <= p < blocks
        if group not in used_groups:
            used_groups[group] = dict(block_bitmap=block_bitmap, inode_bitmap=inode_bitmap,
                                      inode_table=inode_table, descriptor_hex=descriptor.hex())
            block(block_bitmap)
            block(inode_bitmap)
        offset = inode_table * blocksize + index * inode_size
        raw = read_at(offset // blocksize * blocksize, blocksize)[offset % blocksize:offset % blocksize + inode_size]
        mode, uid, size, atime, ctime, mtime, dtime, gid = struct.unpack_from('<HHIIIIIH', raw)
        ptrs = struct.unpack_from('<15I', raw, 40)
        count = (size + blocksize - 1) // blocksize
        assert count <= 12 and size <= 8192, 'Target walk must use small direct-block files'
        assert mode & 0xf000 in (0x4000, 0x8000), 'Unexpected symlink or file type'
        selected = ptrs[:count]
        assert all(firstdata <= p < blocks for p in selected)
        data = b''.join(block(p) for p in selected)[:size]
        item = dict(inode=number, group=group, physical_inode_offset=offset,
                    mode=oct(mode), uid=uid, gid=gid, size=size,
                    atime=atime, ctime=ctime, mtime=mtime, dtime=dtime,
                    links=struct.unpack_from('<H', raw, 26)[0],
                    allocated_sectors=struct.unpack_from('<I', raw, 28)[0],
                    flags=struct.unpack_from('<I', raw, 32)[0],
                    blocks=list(selected), raw_inode_hex=raw.hex(), content_sha256=sha(data))
        nodes.append(item)
        return item, data

    current = 2
    for name in ('bin', 'startBTCore.sh'):
        parent, content = inode(current)
        assert int(parent['mode'], 8) & 0xf000 == 0x4000
        offset, matches = 0, []
        while offset < len(content):
            ino, rec_len, name_len, dtype = struct.unpack_from('<IHBB', content, offset)
            assert rec_len >= 8 and rec_len % 4 == 0 and name_len <= rec_len - 8
            assert offset + rec_len <= len(content) and offset % blocksize + rec_len <= blocksize
            rawname = content[offset + 8:offset + 8 + name_len]
            if ino and rawname == name.encode('ascii'):
                matches.append(ino)
                directories.append(dict(parent_inode=current, name=name, inode=ino,
                                        directory_offset=offset, entry_length=rec_len,
                                        physical_offset=parent['blocks'][offset // blocksize] * blocksize + offset % blocksize,
                                        entry_hex=content[offset:offset + rec_len].hex()))
            offset += rec_len
        assert len(matches) == 1, 'Missing or duplicate target directory entry'
        current = matches[0]
    target, script = inode(current)
    assert int(target['mode'], 8) & 0xf000 == 0x8000
    assert target['size'] == 1283 and sha(script) == EXPECTED_SHA
    return dict(block_size=blocksize, blocks=blocks, filesystem_bytes=blocks * blocksize,
                partition_bytes=partition_size, groups=groups, inode_size=inode_size,
                state=u16(58), errors_policy=u16(60), mount_count=u16(52),
                revision=u32(76), creator_os=u32(72),
                features=dict(compat=u32(92), incompat=u32(96), ro_compat=u32(100)),
                uuid=sb[104:120].hex(), used_group_descriptors=used_groups,
                walk_nodes=nodes, directory_entries=directories, target=target), script
