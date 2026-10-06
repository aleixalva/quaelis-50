import pefile, sys
pe = pefile.PE(sys.argv[1]); needle = sys.argv[2].encode('utf-16-le')
for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    for e in t.directory.entries:
        for l in e.directory.entries:
            d = pe.get_data(l.data.struct.OffsetToData, l.data.struct.Size)
            if needle in d: print(t.name or t.id, e.name or e.id, l.id, len(d))
