import struct, sys
def read(path):
    d=open(path,'rb').read()
    magic=d[:4]
    if magic==b'\x0a\x0d\x0d\x0a': raise SystemExit("pcapng")
    e='<' if magic in (b'\xd4\xc3\xb2\xa1',b'\x4d\x3c\xb2\xa1') else '>'
    lt=struct.unpack(e+'I',d[20:24])[0]
    off=24; out=[]
    while off+16<=len(d):
        ts,tu,cl,ol=struct.unpack(e+'IIII',d[off:off+16]); off+=16
        out.append((ts+tu/1e6,d[off:off+cl])); off+=cl
    return lt,out
if __name__=='__main__':
    lt,pk=read(sys.argv[1]); print('linktype',lt,'n',len(pk))
    t0=pk[0][0]
    for t,p in pk:
        # USBPcap header
        hl,irp,status,func,info,bus,dev,ep,tt,dl=struct.unpack('<HQIHBHHBBI',p[:27])
        rest=p[hl:]
        extra=''
        if tt==2: # control
            stage=p[27]
            if stage==0:
                setup=rest[:8]; rest=rest[8:]; extra='SETUP '+setup.hex(' ')
            else: extra=f'stage{stage}'
        print(f"{t-t0:8.3f} {'IN ' if info&1 else 'OUT'} dev{dev} ep{ep:02x} tt{tt} {extra} [{len(rest)}] {rest.hex()}")
