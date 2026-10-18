"""Lectura / escritura de la fuente de Kamaitachi no Yoru TH (BIN.PAC entrada id 0, sin comprimir).
Formato: tabla de N u16 BIG-endian (desplazamiento en unidades de 4 B) + registros de glifo:
  byte0&0x3f = ancho, byte1&0x3f = alto (bits altos: sin uso observado), luego RLE de nibbles (alto primero):
  n != 0xf -> un pixel de valor n (0..14); 0xf v c -> v repetido (c+4) veces.
El mapa codigo SJIS -> indice esta en el exe (tabla hash 0x8006b754), ver docs/02_fuente_y_texto.md."""
import struct,sys

def leer_pac(d):
    E=[];p=0
    while True:
        i,o=struct.unpack_from('<HH',d,p);p+=4
        if i==0xffff: return E,o
        E.append((i,o))

def entrada(pac_bytes,ident):
    E,fin=leer_pac(pac_bytes); offs=[o for _,o in E]+[fin]
    for k,(i,o) in enumerate(E):
        if i==ident: return pac_bytes[o*2048:offs[k+1]*2048]

def decodificar_registro(blob,rec):
    w=blob[rec]&0x3f; h=blob[rec+1]&0x3f
    pos=0;out=[]
    def nib():
        nonlocal pos
        b=blob[rec+2+(pos>>1)]; v=(b&0xf) if pos&1 else (b>>4); pos+=1; return v
    while len(out)<w*h:
        n=nib()
        if n!=0xf: out.append(n)
        else:
            v=nib(); c=nib()+4; out+=[v]*c
    return w,h,out[:w*h],(pos+1)//2   # bytes de datos usados

def codificar(px):
    """RLE de nibbles; runs de >=4 iguales -> f v (c-4) (max 19)."""
    nibs=[];i=0;n=len(px)
    while i<n:
        v=px[i];j=i
        while j<n and px[j]==v and j-i<19: j+=1
        c=j-i
        if c>=4: nibs+= [0xf,v,c-4]; i=j
        else: nibs.append(v); i+=1
    if len(nibs)&1: nibs.append(0)
    return bytes((nibs[k]<<4)|nibs[k+1] for k in range(0,len(nibs),2))

def leer(blob):
    """-> (lista de glifos [(w,h,px)] por indice, offsets). El numero de glifos = primer offset*4/2."""
    n=struct.unpack_from('>H',blob,0)[0]*4//2
    offs=[struct.unpack_from('>H',blob,2*i)[0] for i in range(n)]
    gl=[decodificar_registro(blob,o*4)[:3] for o in offs]
    return gl,offs

def construir(gl):
    """Reconstruye el blob desde la lista de glifos (registros alineados a 4 B)."""
    n=len(gl); cab=(2*n+3)//4*4
    recs=[]; offs=[]; pos=cab
    for w,h,px in gl:
        r=bytes([w&0x3f,h&0x3f])+codificar(px)
        r+=b'\0'*((-len(r))%4)
        offs.append(pos//4); recs.append(r); pos+=len(r)
    blob=bytearray(struct.pack('>%dH'%n,*offs)); blob+=b'\0'*(cab-len(blob))
    for r in recs: blob+=r
    return bytes(blob)

if __name__=='__main__':
    pac=open(sys.argv[1],'rb').read()
    f=entrada(pac,0)
    gl,offs=leer(f)
    print('glifos:',len(gl),' bytes entrada:',len(f))
    ok=sum(1 for (w,h,px),o in zip(gl,offs) if codificar(px)==f[o*4+2:o*4+2+len(codificar(px))])
    print('re-codificacion identica al original en %d/%d glifos'%(ok,len(gl)))
    nb=construir(gl); gl2,_=leer(nb)
    print('reconstruido: %d B (original %d); decodifica igual: %s'%(len(nb),len(f),gl2==gl))
