import pefile, sys, struct, re
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
for cid in [int(x) for x in sys.argv[2:]]:
    pat = struct.pack('<II', cid, cid)
    for m in re.finditer(re.escape(pat), img):
        o = m.start() - 8
        msg, code = struct.unpack_from('<II', img, o)
        sig, pfn = struct.unpack_from('<II', img, o+16)
        if msg < 0x10000 and 0x401000 <= pfn < 0x600000:
            print(f"id {cid}: msg {msg:#x} code {code:#x} entry {base+o:#x} sig {sig} handler {pfn:#x}")
