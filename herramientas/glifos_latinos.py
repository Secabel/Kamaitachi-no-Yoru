"""Generador de glifos latinos para Kamaitachi no Yoru TH (mismo metodo que Sosei-hen: letra base + marca con borde).
Glifo = (ancho, alto=19, pixeles 0..14 fila a fila). Valores: 0 transparente, 1 borde, 14 relleno.
Metricas de la fuente original: mayusculas filas 1-14, minusculas x-height filas 4-14, ascendentes 1-14, descendentes hasta 16.
Uso: python glifos_latinos.py [mockup.png]   (lee ../extraido/BIN.PAC y ../extraido/SLPS_017.94.text.bin)"""
import struct,os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import fuente_kama as FK
AQUI=os.path.dirname(os.path.abspath(__file__)); EXT=os.path.join(AQUI,'..','extraido')
H=19
_blob=FK.entrada(open(os.path.join(EXT,'BIN.PAC'),'rb').read(),0)
_gl,_offs=FK.leer(_blob)
_exe=open(os.path.join(EXT,'SLPS_017.94.text.bin'),'rb').read()
_HT=0x8006b754-0x80010000
def indice(code):
    v=(code+0x7ec0)&0xffff; h=(v-((v&0xff00)>>2))&0xffff; h=(h*5)&0xfff
    for _ in range(4096):
        c,i=struct.unpack_from('<Hh',_exe,_HT+4*h)
        if c==code: return i
        h=(h+1)&0xfff
def base(ch):
    """glifo original de la letra latina ch (ancho completo SJIS 0x8260.. / 0x8281.. / 0x824f..)"""
    if ch.isdigit(): code=0x824f+int(ch)
    elif ch.isupper(): code=0x8260+ord(ch)-65
    elif ch.islower(): code=0x8281+ord(ch)-97
    else: code={'?':0x8148,'!':0x8149,':':0x8146}[ch]
    w,h,px=_gl[indice(code)]
    return [list(px[y*w:(y+1)*w]) for y in range(h)]
def a_glifo(M):
    return len(M[0]),len(M),[v for r in M for v in r]
def borde(E):
    xs=[x for x,y in E]; ys=[y for x,y in E]
    W=max(xs)+3; Hh=max(ys)+3; a=[[0]*W for _ in range(Hh)]
    for x,y in E:
        for dx in(-1,0,1):
            for dy in(-1,0,1): a[y+1+dy][x+1+dx]=1
    for x,y in E: a[y+1][x+1]=14
    return a
MARCAS={'acute':[(2,0),(3,0),(1,1),(2,1),(0,2),(1,2)],'diaer':[(0,0),(1,0),(0,1),(1,1),(4,0),(5,0),(4,1),(5,1)],
        'tilde':[(0,2),(1,1),(2,1),(3,2),(4,2),(5,1),(6,1)]}
MARCAS_MAY=MARCAS   # mismas marcas de 3 filas: su borde inferior coincide con el contorno superior de la mayuscula (fila 3)
def pegar(M,mark,cx,ytop,sin_borde_sup=True):
    a=borde(mark); 
    if sin_borde_sup: a=a[1:]          # el borde superior se pierde (sin filas libres)
    h=len(a); w=len(a[0]); x0=cx-w//2
    for y in range(h):
        for x in range(w):
            yy=ytop+y; xx=x0+x
            if a[y][x] and 0<=yy<len(M) and 0<=xx<len(M[0]):
                if a[y][x]==14 or M[yy][xx]==0: M[yy][xx]=a[y][x]
def quitar_filas(M,rows):
    return [r for i,r in enumerate(M) if i not in rows]
def comprimir_mayuscula(M):
    """quita 2 filas interiores casi redundantes y baja el glifo para dejar filas 0-2 libres (la linea base queda en la fila 14)"""
    ini=min(y for y,r in enumerate(M) if any(r)); fin=max(y for y,r in enumerate(M) if any(r))
    cand=[]
    for y in range(ini+3,fin-3):
        d=sum(abs(a-b) for a,b in zip(M[y],M[y+1])); cand.append((d,y))
    cand.sort(); ya=cand[0][1]
    yb=min((y for d,y in cand if abs(y-ya)>1),key=lambda y:dict((yy,dd) for dd,yy in cand)[y])
    M2=quitar_filas(M,{ya,yb})                      # glifo de 17 filas -> quedan 17
    w=len(M[0])
    M2=[[0]*w for _ in range(3)]+[r[:] for r in M2[1:]]   # fila 0 original (vacia) fuera; el glifo empieza en la fila 3
    M2+=[[0]*w for _ in range(H)]                          # filas independientes (no repetir el mismo objeto)
    return M2[:H]
def acentuada(ch,marca):
    M=base(ch)
    mayus=ch.isupper()
    if ch=='i':                                      # quitar el punto
        for y in range(1,4): M[y]=[0]*len(M[0])
    if mayus:
        M=comprimir_mayuscula(M)
    marks=MARCAS_MAY if mayus else MARCAS
    wm=len(borde(marks[marca])[0])                    # ancho de la marca con borde
    if wm>len(M[0]):                                  # glifo mas estrecho que la marca: ensanchar centrado
        pad=wm-len(M[0]); izq=pad//2
        M=[[0]*izq+r+[0]*(pad-izq) for r in M]
    pegar(M,marks[marca],len(M[0])//2,0,sin_borde_sup=True)
    return a_glifo(M)
def volteada(ch):
    M=base(ch); rows=[y for y,r in enumerate(M) if any(r)]; a,b=rows[0],rows[-1]
    N=[r[:] for r in M]; N[a:b+1]=[r[::-1] for r in M[a:b+1][::-1]]
    return a_glifo(N)
def sello(E,ancho=None):
    a=borde(E); W=len(a[0]); M=[[0]*W for _ in range(H)]
    return a,W
def puntuacion():
    """. , ; - ' y espacio nuevos con el mismo borde (relleno 14, borde 1)."""
    out={}
    def poner(E,dy):
        a=borde(E); W=len(a[0]); M=[[0]*W for _ in range(H)]
        for y,r in enumerate(a):
            if 0<=y+dy<H: M[y+dy]=r[:]
        return a_glifo(M)
    out['.']=poner([(0,0),(1,0),(0,1),(1,1)],12)
    out[',']=poner([(1,0),(2,0),(1,1),(2,1),(0,2),(1,2)],12)
    out[';']=None  # se arma abajo
    out['-']=poner([(0,0),(1,0),(2,0),(3,0)],8)
    out["'"]=poner([(1,0),(2,0),(1,1),(2,1),(0,2),(1,2)],1)
    # punto y coma: dos puntos con cola
    a1=borde([(0,0),(1,0),(0,1),(1,1)]); a2=borde([(1,0),(2,0),(1,1),(2,1),(0,2),(1,2)])
    W=max(len(a1[0]),len(a2[0])); M=[[0]*W for _ in range(H)]
    for y,r in enumerate(a1): M[7+y][:len(r)]=r
    for y,r in enumerate(a2): M[12+y][:len(r)]=r
    out[';']=a_glifo(M)
    out[' ']=(11,H,[0]*(11*H))
    return out
def todos():
    g={}
    for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789?!:':
        g[ch]=a_glifo(base(ch))
    for ch,m in (('á','acute'),('é','acute'),('í','acute'),('ó','acute'),('ú','acute'),('ñ','tilde'),('ü','diaer'),
                 ('Á','acute'),('É','acute'),('Í','acute'),('Ó','acute'),('Ú','acute'),('Ñ','tilde'),('Ü','diaer')):
        g[ch]=acentuada({'á':'a','é':'e','í':'i','ó':'o','ú':'u','ñ':'n','ü':'u'}.get(ch,ch.translate(str.maketrans('ÁÉÍÓÚÑÜ','AEIOUNU'))),m)
    g['¿']=volteada('?'); g['¡']=volteada('!')
    g.update({k:v for k,v in puntuacion().items()})
    return g
def render(lineas,g,escala=3,bg=(58,40,20)):
    from PIL import Image
    ancho=max(sum(g[c][0]+1 for c in l) for l in lineas)+8
    img=Image.new('RGB',((ancho)*escala,(len(lineas)*22+6)*escala),bg)
    for n,l in enumerate(lineas):
        x=4;y=3+n*22
        for c in l:
            w,h,px=g[c]
            for yy in range(h):
                for xx in range(w):
                    v=px[yy*w+xx]
                    if v:
                        t=int(255*v/14) if v>1 else 0
                        col=(t,t,t) if v>1 else (10,10,10)
                        for dy in range(escala):
                            for dx in range(escala): img.putpixel(((x+xx)*escala+dx,(y+yy)*escala+dy),col)
            x+=w+1
    return img
FRASES=['Camion, senor. Que? Ultimo Ninos Aqui','Camión, señor. ¿Qué? Último Niños Aquí','ÁÉÍÓÚÑ áéíóú ñ ü ¿i','Él dijo: ¡Está aquí! ¿Cómo lo sabías?; sí - no.']
if __name__=='__main__':
    g=todos()
    sal=sys.argv[1] if len(sys.argv)>1 else os.path.join(AQUI,'..','analisis','mockup_latino_kamaitachi.png')
    render(FRASES,g).save(sal); print('mockup ->',sal,' glifos:',len(g))

ICONOS = {0x848f: 'Tarjeta', 0x8490: 'Ajustes', 0x8491: 'R1:Pág'} if os.environ.get('KAMA_LANG', 'es') != 'en' else {0x848f: 'Card', 0x8490: 'Settings', 0x8491: 'R1:Page'}      # glifos-icono del original (rotulo 'メモリーカード' de 57 px): se sustituyen por texto latino (<=63 px)
def texto_glifo(txt):
    t = todos(); cols = []                       # lista de columnas (cada una H pixeles)
    for k, c in enumerate(txt):
        w, h, p = t[c]
        n = w - (1 if k < len(txt) - 1 and sum(t[x][0] for x in txt) > 63 else 0)   # si no cabe, recorta 1 px (borde) por letra
        for x in range(n): cols.append([p[y*w + x] for y in range(H)])
    W = len(cols); assert W <= 63, (txt, W)
    return (W, H, [cols[x][y] for y in range(H) for x in range(W)])
