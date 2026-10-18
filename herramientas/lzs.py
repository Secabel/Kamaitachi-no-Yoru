"""LZSS del juego (cargador 0x800355cc): anillo de 4096 con 0x20 en 0..0xfed, escritura desde 0xfee, banderas LSB-first (1 = literal),
par (b0, b1): posicion absoluta = b0 | (b1&0xf0)<<4, longitud = (b1&15)+3.  descomprimir(datos, n) lee n bytes de entrada."""
def descomprimir(src, n=None):
    n = len(src) if n is None else n
    ring = bytearray([0x20]) * 4096; r = 0xfee; out = bytearray(); i = 0
    while i < n:
        fl = src[i]; i += 1
        for b in range(8):
            if i >= n: break
            if fl >> b & 1:
                c = src[i]; i += 1; out.append(c); ring[r] = c; r = (r + 1) & 4095
            else:
                if i + 1 >= n + 0 and i + 1 > n - 0: 
                    if i + 1 >= n + 1: break
                b0 = src[i]; b1 = src[i+1]; i += 2
                p = b0 | (b1 & 0xf0) << 4
                for j in range((b1 & 15) + 3):
                    c = ring[(p + j) & 4095]; out.append(c); ring[r] = c; r = (r + 1) & 4095
    return bytes(out)
def comprimir(dat):
    """analisis optimo (DP) sobre el flujo virtual con 0xfee espacios previos; devuelve bytes"""
    n = len(dat); PRE = 0xfee
    V = bytes([0x20]) * PRE + bytes(dat)          # indice virtual i+PRE
    INF = 1 << 30
    best = [INF] * (n + 1); best[0] = 0; prev = [None] * (n + 1)
    from collections import defaultdict
    pos = defaultdict(list)
    for k in range(len(V) - 2): pos[V[k:k+3]].append(k)
    for i in range(n):
        if best[i] >= INF: continue
        vi = i + PRE
        c = best[i] + 9
        if c < best[i+1]: best[i+1] = c; prev[i+1] = (i, 0, 0)
        if i + 3 <= n:
            L0 = 0; bp = -1
            cand = pos.get(V[vi:vi+3], [])
            # candidatos anteriores dentro de la ventana
            import bisect
            lo = bisect.bisect_left(cand, vi - 4095); hi = bisect.bisect_left(cand, vi)
            lens = {}
            for p in cand[lo:hi]:
                L = 3
                while L < 18 and vi + L < len(V) and V[p + L] == V[vi + L]: L += 1      # solape permitido (p+L<vi+L)
                if L > L0: L0 = L; bp = p
                lens[p] = L
            if L0 >= 3:
                for L in range(3, L0 + 1):
                    c = best[i] + 17
                    if c < best[i+L]: best[i+L] = c; prev[i+L] = (i, L, bp)
    toks = []; i = n
    while i > 0:
        a, L, p = prev[i]; toks.append((L, p)); i = a
    toks.reverse(); out = bytearray(); k = 0; i = 0
    while k < len(toks):
        grp = toks[k:k+8]; fl = 0; body = bytearray()
        for b, (L, p) in enumerate(grp):
            if L == 0: fl |= 1 << b; body.append(dat[i]); i += 1
            else:
                ring = (p) & 4095       # p ya es indice virtual con PRE: posicion anillo = p mod 4096 (PRE=0xfee ya incluido)
                body += bytes([ring & 255, ((ring >> 4) & 0xf0) | (L - 3)]); i += L
        out.append(fl); out += body; k += 8
    return bytes(out)
