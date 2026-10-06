import pefile, sys, struct
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
a, b = int(sys.argv[2], 16), int(sys.argv[3], 16)
def ws(va):
    o = va - base; e = o
    while e < len(img)-1 and img[e:e+2] != b'\0\0': e += 2
    return img[o:e].decode('utf-16-le', 'replace')
for va in range(a, b, 4):
    p = struct.unpack_from('<I', img, va-base)[0]
    if 0x5b0000 <= p < 0x600000:
        s = ws(p)
        print(f"{va:#x} -> {p:#x} {s[:60]!r}")
    else:
        print(f"{va:#x}    {p:#x}")
