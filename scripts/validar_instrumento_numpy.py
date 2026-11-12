"""
validar_instrumento_numpy.py
Prueba numerica (sin GNU Radio ni hardware) de la cadena de medicion BER:
    PRBS-15 -> BPSK -> RRC (beta=0.5, 8 sps) -> canal (retardo 37 muestras, giro 180 grados)
    -> e_EbN0_Sweep -> filtro acoplado + muestreo ideal -> decision
    -> [retardo lat_comp en ambas ramas] -> e_Ref_PRBS15_Rx -> e_BER_Curve

Ejecuta los MISMOS archivos .py de los Embedded Python Blocks (sin modificarlos)
usando un sustituto minimo de 'gnuradio.gr' si GNU Radio no esta instalado.

Objetivos:
  1) comprobar que el ruido de e_EbN0_Sweep produce exactamente la BER teorica
     Q(sqrt(2Eb/N0)) con un receptor ideal (calibracion del instrumento);
  2) comprobar que e_Ref_PRBS15_Rx alinea y corrige la ambiguedad de 180 grados;
  3) mostrar el efecto de la latencia del receptor sobre la segmentacion del
     barrido (lat_comp_bits = 0 vs 400).

Uso:  python scripts/validar_instrumento_numpy.py [barridos] [lat_comp_bits ...]
      python scripts/validar_instrumento_numpy.py 2 0 400
"""
import os
import sys
import types
import importlib.util
import numpy as np
from math import erfc, sqrt

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INS = os.path.join(RAIZ, 'grc', 'instrumentacion')

try:
    from gnuradio import gr  # noqa: F401
except ImportError:          # sustituto minimo: solo las clases base que usan los bloques
    gr = types.ModuleType('gnuradio.gr')

    class sync_block:
        def __init__(self, name='', in_sig=None, out_sig=None):
            self.name = name

    class sync_decimator(sync_block):
        def __init__(self, name='', in_sig=None, out_sig=None, decim=1):
            super().__init__(name, in_sig, out_sig)
            self.decim = decim
    gr.sync_block, gr.sync_decimator, gr.decim_block = sync_block, sync_decimator, sync_decimator
    pkg = types.ModuleType('gnuradio')
    pkg.gr = gr
    sys.modules['gnuradio'] = pkg
    sys.modules['gnuradio.gr'] = gr


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, os.path.join(INS, nombre + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rrc(gain, fs, rs, alpha, ntaps):
    """Copia de gr::filter::firdes::root_raised_cosine."""
    ntaps |= 1
    spb = fs / rs
    taps = np.zeros(ntaps)
    scale = 0.0
    for i in range(ntaps):
        k = i - ntaps // 2
        x1 = np.pi * k / spb
        x2 = 4 * alpha * k / spb
        x3 = x2 * x2 - 1
        if abs(x3) >= 1e-6:
            num = (np.cos((1 + alpha) * x1) + np.sin((1 - alpha) * x1) / (4 * alpha * k / spb)) if k != 0 \
                else np.cos((1 + alpha) * x1) + (1 - alpha) * np.pi / (4 * alpha)
            den = x3 * np.pi
        else:
            x3 = (1 - alpha) * x1
            x2 = (1 + alpha) * x1
            num = (np.sin(x2) * (1 + alpha) * np.pi - np.cos(x3) * ((1 - alpha) * np.pi * spb) / (4 * alpha * k)
                   + np.sin(x3) * spb * spb / (4 * alpha * k * k))
            den = -32 * np.pi * alpha * alpha * k / spb
        taps[i] = 4 * alpha * num / den
        scale += taps[i]
    return taps * gain / scale


def correr(barridos, K, Sps=8, Rs=8000.0, beta=0.5, span=11, d0=37):
    fs = Rs * Sps
    tx = cargar('e_PRBS15_Tx').blk()
    ref_blk = cargar('e_Ref_PRBS15_Rx').blk()
    sweep = cargar('e_EbN0_Sweep').blk(samp_rate=fs, bit_rate=Rs)
    curva = cargar('e_BER_Curve').blk()
    nbits = int(15 * 101000 * barridos) + 2000
    bits = np.empty(nbits, np.uint8)
    tx.work([], [bits])
    up = np.zeros(nbits * Sps)
    up[::Sps] = 2.0 * bits - 1.0
    h = rrc(Sps, fs, Rs, beta, span * Sps)
    s = np.convolve(up, h)[:nbits * Sps]
    x = (0.05 * np.exp(1j * np.pi) * np.concatenate((np.zeros(d0), s))[:len(s)]).astype(np.complex64)
    y = np.empty_like(x)
    eb = np.empty(len(x), np.float32)
    for a in range(0, len(x), 8192):
        b = min(a + 8192, len(x))
        sweep.work([x[a:b]], [y[a:b], eb[a:b]])
    mf = np.convolve(y, rrc(1.0, fs, Rs, beta, span * Sps))
    retardo = d0 + 2 * (((span * Sps) | 1) // 2)        # retardo de grupo Tx + Rx
    rx = (np.real(mf[retardo::Sps][:nbits - 200]) > 0).astype(np.uint8)
    rx = np.concatenate((np.zeros(K, np.uint8), rx))          # blocks.delay en ambas ramas
    ref = np.empty(len(rx), np.uint8)
    ber_l = np.empty(len(rx), np.float32)
    for a in range(0, len(rx), 4096):
        b = min(a + 4096, len(rx))
        ref_blk.work([rx[a:b]], [ref[a:b], ber_l[a:b]])
    n = (len(rx) // 1000) * 1000
    nout = n // 1000
    ob = np.zeros((nout, curva.N), np.float32)
    ol = np.zeros((nout, curva.N), np.float32)
    for k in range(0, nout, 50):
        kk = min(k + 50, nout)
        curva.work([ref[k * 1000:kk * 1000].astype(np.int8), rx[k * 1000:kk * 1000].astype(np.int8)],
                   [ob[k:kk], ol[k:kk]])
    return curva


def main():
    barridos = float(sys.argv[1]) if len(sys.argv) > 1 else 2
    Ks = [int(v) for v in sys.argv[2:]] or [0, 400]
    filas = []
    res = {K: correr(barridos, K) for K in Ks}
    eb = res[Ks[0]].eb_axis
    print('Eb/N0  teoria     ' + '  '.join('lat_comp=%-4d errores/bits      BER' % K for K in Ks))
    for i, e in enumerate(eb):
        t = 0.5 * erfc(sqrt(10 ** (e / 10)))
        celdas = []
        fila = [e, t]
        for K in Ks:
            c = res[K]
            celdas.append('%7d/%7d  %9.2e' % (c.errors[i], c.count[i], c.errors[i] / max(c.count[i], 1)))
            fila += [int(c.errors[i]), int(c.count[i])]
        filas.append(fila)
        print('%5.1f  %.2e   ' % (e, t) + '   '.join(celdas))
    out = os.path.join(RAIZ, 'resultados', 'simulacion', 'validacion_instrumento_numpy.csv')
    with open(out, 'w') as f:
        f.write('EbN0_dB,BER_teorica,' + ','.join('errores_K%d,bits_K%d' % (K, K) for K in Ks) + '\n')
        for fila in filas:
            f.write('%.1f,%.4e,' % (fila[0], fila[1]) + ','.join(str(v) for v in fila[2:]) + '\n')
    print('->', os.path.relpath(out, RAIZ))


if __name__ == '__main__':
    main()
