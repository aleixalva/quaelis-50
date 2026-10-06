import pefile, sys, struct, re
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
md = Cs(CS_ARCH_X86, CS_MODE_32)
iat = {i.name.decode(): i.address for e in pe.DIRECTORY_ENTRY_IMPORT if b'SLAB' in e.dll for i in e.imports}
def dis(va, n=40):
    for ins in md.disasm(img[va-base:va-base+n*8], va):
        yield ins
for name in sys.argv[2:]:
    pat = b'\xff\x15' + struct.pack('<I', iat[name])
    sites = [base + m.start() for m in re.finditer(re.escape(pat), img)]
    print(name, hex(iat[name]), [hex(s) for s in sites])
