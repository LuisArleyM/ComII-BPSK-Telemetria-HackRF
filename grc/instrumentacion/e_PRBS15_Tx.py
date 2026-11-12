"""
e_PRBS15_Tx
Fuente de bits de prueba CONOCIDA para el transmisor BPSK.

Secuencia PRBS-15 (ITU-T O.150), polinomio x^15 + x^14 + 1,
registro LFSR iniciado en 'seed' (por defecto todos unos, 0x7FFF).
Periodo: 2^15 - 1 = 32767 bits.

Salida 0 : bits 0/1 (byte), uno por simbolo BPSK (Rb = Rs).

Por que PRBS y no Random Source:
    El Tx y el Rx se ejecutan en computadores distintos. Para calcular una
    BER valida, el receptor debe conocer exactamente la misma secuencia
    (Guia 4, "Tx y Rx en computadores diferentes"). Una PRBS es repetible,
    tiene densidad de unos ~1/2 y cualquier ventana de 15 bits o mas es unica
    dentro del periodo, lo que permite alinear la referencia por correlacion.

La derivacion de la secuencia binaria ANTES de la modulacion (Guia 4, paso 6)
es la salida de este bloque.
"""

import numpy as np
from gnuradio import gr


def prbs15(seed=0x7FFF):
    """Devuelve un periodo completo (32767 bits) de la PRBS-15 x^15+x^14+1."""
    state = int(seed) & 0x7FFF
    if state == 0:
        state = 0x7FFF
    out = np.empty(32767, dtype=np.uint8)
    for i in range(32767):
        newbit = ((state >> 14) ^ (state >> 13)) & 1
        state = ((state << 1) | newbit) & 0x7FFF
        out[i] = newbit
    return out


class blk(gr.sync_block):
    def __init__(self, seed=32767):
        gr.sync_block.__init__(
            self,
            name='e_PRBS15_Tx',
            in_sig=None,
            out_sig=[np.uint8]
        )
        self.seed = int(seed)
        self.seq = prbs15(self.seed)
        self.L = len(self.seq)
        self.pos = 0
        print('[TX] PRBS-15 x^15+x^14+1, periodo %d bits, seed=0x%04X'
              % (self.L, self.seed))

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        if n <= 0:
            return 0
        idx = (self.pos + np.arange(n, dtype=np.int64)) % self.L
        out[:] = self.seq[idx]
        self.pos = int((self.pos + n) % self.L)
        return n
