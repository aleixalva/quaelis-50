import pefile, sys, struct, re
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
for name in sys.argv[2:]:
    for enc in (name.encode()+b'\0', name.encode('utf-16-le')+b'\0\0'):
        for m in re.finditer(re.escape(enc), img):
            va = base + m.start()
            refs = [base + r.start() for r in re.finditer(re.escape(struct.pack('<I', va)), img)]
            print(name, hex(va), [hex(r) for r in refs])
