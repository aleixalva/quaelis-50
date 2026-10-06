# linear sweep disassembly of .text to a file, with import names
import pefile, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
iat = {f"{i.address:#x}": i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
sec = [s for s in pe.sections if s.Name.startswith(b'.text')][0]
a = base + sec.VirtualAddress; end = a + sec.Misc_VirtualSize
md = Cs(CS_ARCH_X86, CS_MODE_32); md.skipdata = True
out = open(sys.argv[2], 'w')
for ins in md.disasm(img[a-base:end-base], a):
    s = f"{ins.address:#x}: {ins.mnemonic} {ins.op_str}"
    if '[0x5' in ins.op_str:
        k = ins.op_str.split('[')[1].split(']')[0]
        if k in iat: s += f"   ; {iat[k]}"
    out.write(s + "\n")
