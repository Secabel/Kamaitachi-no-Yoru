"""Decompressor for the game's 'ike' format (magic 9d 89 'ike').
It runs the game's own routine (0x800356c8) in the Unicorn emulator, so no reverse-engineered port is needed.
Only the executable is required: pass its bytes (text part, i.e. SLPS_017.94 without the 0x800 header) or let it be loaded
from extraido/SLPS_017.94.  Returns (data, size).  The size is taken from the output pointer ($t3), because the 16-bit
size stored in the header wraps around for images larger than 64 KB."""
import os
from unicorn import Uc, UcError, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_SP, UC_MIPS_REG_RA, UC_MIPS_REG_T3

MAGIC = bytes.fromhex('9d89696b65')
_AQUI = os.path.dirname(os.path.abspath(__file__))
_exe = None

def texto_exe():
    """Bytes of the executable's text part (file offset 0x800 onwards), loaded from extraido/SLPS_017.94."""
    global _exe
    if _exe is None:
        _exe = open(os.path.join(_AQUI, '..', 'extraido', 'SLPS_017.94'), 'rb').read()[0x800:]
    return _exe

def descomprimir(src, exe=None, maxout=0x40000):
    mu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 + UC_MODE_LITTLE_ENDIAN)
    mu.mem_map(0, 0x200000); mu.mem_write(0x10000, exe if exe is not None else texto_exe())
    S = 0x80100000; Dd = 0x80140000
    mu.mem_write(S & 0x1fffffff, src + b'\0' * 16)
    mu.reg_write(UC_MIPS_REG_A0, S); mu.reg_write(UC_MIPS_REG_A1, Dd)
    mu.reg_write(UC_MIPS_REG_SP, 0x801f0000); RA = 0x80001000; mu.reg_write(UC_MIPS_REG_RA, RA)
    try: mu.emu_start(0x800356c8, RA, count=30_000_000)
    except UcError as e: return None, str(e)
    n = mu.reg_read(UC_MIPS_REG_T3) - Dd
    return bytes(mu.mem_read(Dd & 0x1fffffff, min(n, maxout))), n
