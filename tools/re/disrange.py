import pefile, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
iat = {i.address: i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
a, b = int(sys.argv[2], 16), int(sys.argv[3], 16)
md = Cs(CS_ARCH_X86, CS_MODE_32)
for ins in md.disasm(img[a-base:b-base], a):
    s = f"{ins.address:#x}: {ins.mnemonic} {ins.op_str}"
    for k, v in iat.items():
        if f"{k:#x}" in ins.op_str: s += f"   ; {v}"
    print(s)
