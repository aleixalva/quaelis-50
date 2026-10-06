import pefile, sys, struct
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image(); base = pe.OPTIONAL_HEADER.ImageBase
a = int(sys.argv[2], 16) - base; n = int(sys.argv[3])
for i in range(n):
    e = struct.unpack_from('<IIIIII', img, a + 24*i)
    print(f"{base+a+24*i:#x} msg {e[0]:#06x} code {e[1]:#06x} id {e[2]}-{e[3]} sig {e[4]} fn {e[5]:#x}")
