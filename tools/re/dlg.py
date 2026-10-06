import pefile, sys, struct
pe = pefile.PE(sys.argv[1]); want = [int(x) for x in sys.argv[2:]]
def sz(d, o):
    if struct.unpack_from('<H', d, o)[0] == 0xFFFF: return struct.unpack_from('<H', d, o+2)[0], o+4
    e = o
    while d[e:e+2] != b'\0\0': e += 2
    return d[o:e].decode('utf-16-le'), e+2
al = lambda o, n=4: (o + n-1) & ~(n-1)
for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    if t.id != 5: continue
    for e in t.directory.entries:
        if e.id not in want: continue
        l = e.directory.entries[0]
        d = pe.get_data(l.data.struct.OffsetToData, l.data.struct.Size)
        assert d[2:4] == b'\xff\xff'
        style = struct.unpack_from('<I', d, 12)[0]; n = struct.unpack_from('<H', d, 16)[0]
        o = 26
        menu, o = sz(d, o); cls, o = sz(d, o); title, o = sz(d, o)
        if style & 0x40: o += 6; font, o = sz(d, o)
        print(f"DIALOG {e.id} '{title}' {n} items")
        for i in range(n):
            o = al(o)
            st = struct.unpack_from('<I', d, o+8)[0]; x,y,w,h = struct.unpack_from('<hhhh', d, o+12); cid = struct.unpack_from('<I', d, o+20)[0]
            o += 24; c, o = sz(d, o); txt, o = sz(d, o); ex = struct.unpack_from('<H', d, o)[0]; o += 2 + ex
            cn = {0x80:'Button',0x81:'Edit',0x82:'Static',0x85:'ComboBox'}.get(c, c)
            print(f"  id={cid:5d} {cn:14} {txt!r:28} at {x},{y} {w}x{h}")
