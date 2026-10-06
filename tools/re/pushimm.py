import pefile, sys, struct, re
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
for v in sys.argv[2:]:
    v = int(v, 0)
    print(v, [hex(base+m.start()) for m in re.finditer(re.escape(b'\x68' + struct.pack('<I', v)), img)][:20])
