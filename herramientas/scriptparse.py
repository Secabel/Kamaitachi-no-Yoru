import json,struct,os,sys
from collections import Counter,defaultdict
D=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'deltas.json')))
SZ={int(k):v[0] for k,v in D.items()}
SZ.update({0x01:2,0x02:2,0x03:0,0x0e:3,0x16:0,0x24:3,0x54:5,0x56:4,0x5d:5})
JUMPS={0x01,0x02,0x03,0x0e,0x16,0x24,0x54,0x56,0x5d}
VAR={0x17,0x65}
base=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','extraido')+os.sep
d=open(base+'SCE.PAC','rb').read()
def pac(d):
    E=[];p=0
    while True:
        i,o=struct.unpack_from('<HH',d,p);p+=4
        if i==0xffff: return E,o
        E.append((i,o))
E,fin=pac(d); offs=[o for _,o in E]+[fin]
ents={a:d[o*2048:offs[k+1]*2048] for k,(a,o) in enumerate(E)}
def frags(e):
    tb=int.from_bytes(e[:2],'little'); of=[int.from_bytes(e[x:x+2],'little') for x in range(0,tb,2)]
    return list(zip(of,of[1:]+[len(e)]))
def parse(fr):
    """devuelve (lista de (pos,op,args|texto), motivo_fin)"""
    p=0;out=[]
    while p<len(fr):
        op=fr[p]
        if op==0:
            q=p+1
            while q<len(fr) and fr[q]!=0: q+= 2 if fr[q]>=0x80 else 1
            if q>=len(fr): return out,'texto sin NUL'
            out.append((p,0,fr[p+1:q])); p=q+1; continue
        if op>=0xca: return out,'opcode>=ca (%02x)'%op
        if op==0x17:
            q=p+2
            while q<len(fr) and fr[q]!=0: q+= 2 if fr[q]>=0x80 else 1
            if q>=len(fr): return out,'texto17 sin NUL'
            out.append((p,0x17,fr[p+1:q])); p=q+1; continue
        n=SZ[op]
        if op==0x13 and p+1<len(fr): n=2+2*(fr[p+1]+1)
        if op==0x57 and p+1<len(fr): n=2+4*(fr[p+1]+1)
        if p+1+n>len(fr): return out,'operandos exceden (%02x)'%op
        out.append((p,op,fr[p+1:p+1+n])); p+=1+n
    return out,'ok'
if __name__=='__main__':
    tot=Counter(); mot=Counter(); ops=Counter()
    for a,e in ents.items():
        if e[:5]==bytes.fromhex('9d89696b65'): continue
        for s,t in frags(e):
            r,m=parse(e[s:t]); tot['frags']+=1
            mot[m.split(' (')[0] if 'opcode' not in m else m]+=1
            for _,op,_ in r: ops[op]+=1
    print(tot); print(mot.most_common(12))
