"""
ejecutar_y_capturar.py
Compila TODOS los .grc del proyecto con el compilador de GNU Radio (grcc),
ejecuta los flujogramas de simulacion y guarda capturas PNG de cada grafica
QT GUI, la curva BER simulada (CSV) y un registro de consola.

Uso (desde "Radioconda Prompt", en la carpeta raiz del repositorio):
    python scripts\\ejecutar_y_capturar.py            -> todo
    python scripts\\ejecutar_y_capturar.py compilar   -> solo validar los .grc
    python scripts\\ejecutar_y_capturar.py beta       -> capturas fase beta
    python scripts\\ejecutar_y_capturar.py sim        -> curva BER simulada
    python scripts\\ejecutar_y_capturar.py limpio     -> prueba de BER en condicion limpia
    python scripts\\ejecutar_y_capturar.py diagramas  -> PNG de cada flujograma

Los flujogramas de hardware (HackRF) solo se compilan: necesitan los radios.
"""
import os
import sys
import glob
import time
import shutil
import importlib
import subprocess
import traceback

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BUILD = os.path.join(RAIZ, 'build_grc')
IMG = os.path.join(RAIZ, 'docs', 'img')
LOG = os.path.join(RAIZ, 'resultados', 'simulacion', 'registro_ejecucion.txt')
# En Windows el modo 'offscreen' de Qt no dibuja texto (sin fuentes): por defecto
# se usan ventanas visibles. CAPTURA_OFFSCREEN=1 fuerza el modo sin ventanas.
OFFSCREEN = os.environ.get('CAPTURA_OFFSCREEN', '0') == '1'


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


def compilar(grc, outdir):
    os.makedirs(outdir, exist_ok=True)
    cmd = [sys.executable, '-c',
           'import sys; from gnuradio.grc.compiler import main; '
           'sys.argv=["grcc","-o",sys.argv[1],sys.argv[2]]; main()', outdir, grc]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0
    print('[grcc] %-38s %s' % (os.path.basename(grc), 'OK' if ok else 'ERROR'))
    if not ok or 'rror' in (r.stdout + r.stderr):
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
    return ok


def todos_los_grc():
    return sorted(glob.glob(os.path.join(RAIZ, 'grc', 'fase*', '*.grc')))


def paso_compilar():
    res = {}
    for g in todos_los_grc():
        res[os.path.basename(g)] = compilar(g, BUILD)
    return res


def cargar(fid):
    if BUILD not in sys.path:
        sys.path.insert(0, BUILD)
    for k in list(sys.modules):
        if k.startswith(fid):
            del sys.modules[k]
    mod = importlib.import_module(fid)
    return getattr(mod, fid)


def hay_offscreen():
    try:
        from PyQt5.QtCore import QLibraryInfo
        plug = QLibraryInfo.location(QLibraryInfo.PluginsPath)
        return any(os.path.exists(os.path.join(plug, 'platforms', f))
                   for f in ('qoffscreen.dll', 'libqoffscreen.so', 'libqoffscreen.dylib'))
    except Exception:
        return False


def app_qt():
    if OFFSCREEN and hay_offscreen():
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        print('[qt] modo offscreen')
    else:
        print('[qt] modo visible (se abriran ventanas)')
    from PyQt5 import Qt
    app = Qt.QApplication.instance() or Qt.QApplication(sys.argv)
    return Qt, app


def esperar(app, seg):
    t0 = time.time()
    while time.time() - t0 < seg:
        app.processEvents()
        time.sleep(0.02)


def capturar(tb, nombres, destino, prefijo, app):
    os.makedirs(destino, exist_ok=True)
    for n in nombres:
        w = getattr(tb, '_%s_win' % n, None)
        if w is None:
            print('   (sin widget %s)' % n)
            continue
        app.processEvents()
        ruta = os.path.join(destino, '%s_%s.png' % (prefijo, n))
        w.grab().save(ruta)
        print('   captura ->', os.path.relpath(ruta, RAIZ))


def preparar(tb, nombres, Qt, ancho=1100, alto=430):
    for n in nombres:
        w = getattr(tb, '_%s_win' % n, None)
        if w is not None:
            w.setMinimumSize(ancho, alto)
    tb.resize(1200, 900)


# ------------------------------------------------------------------ fase beta
def paso_beta():
    Qt, app = app_qt()
    niveles = [('referencia', 0.0), ('suave', 0.3), ('media', 0.6), ('fuerte', 1.0)]
    for fid, sinks in (('Enlace_Beta_Impulsivo_BPSK', ['tiempo', 'psd', 'constelacion']),
                       ('Enlace_Beta_Impulsivo_BFSK', ['tiempo', 'psd', 'plano_iq'])):
        cls = cargar(fid)
        tb = cls()
        preparar(tb, sinks, Qt)
        tb.start()
        tb.show()
        for nombre, a in niveles:
            tb.set_A_imp(a)
            tb.set_noise_amp(0.10)
            esperar(app, 4.0)
            print('[beta] %s nivel=%s A_imp=%.1f noise_amp=0.10' % (fid, nombre, a))
            capturar(tb, sinks, os.path.join(IMG, 'fase2'),
                     '%s_%s' % ('bpsk' if 'BPSK' in fid else 'bfsk', nombre), app)
        tb.stop()
        tb.wait()
        tb.close()
        del tb


# ------------------------------------------------------------------ simulacion BER
def paso_sim(barridos=5, timeout=1500):
    if not os.path.exists(os.path.join(BUILD, 'SIM_LAZO_BPSK_BER.py')):
        print('[sim] SIM_LAZO_BPSK_BER no compilo; revise el paso compilar')
        return
    Qt, app = app_qt()
    cls = cargar('SIM_LAZO_BPSK_BER')
    tb = cls()
    tb.set_acelerar(100000)          # sin limite practico de velocidad
    import math
    tb.set_costas_bw(2 * math.pi / costas_den())
    print('[sim] costas_bw = 2*pi/%d' % costas_den())
    sinks = ['curva_ber', 'rx_const_sincronizada', 'rx_espectro_barrido', 'offset_hz',
             'ebn0_actual', 'ber_desde_enganche']
    preparar(tb, sinks, Qt)
    t0 = time.time()
    tb.start()
    tb.show()
    blk = tb.e_BER_Curve
    meta = barridos * blk.bits_por_punto
    capt_media = False
    while time.time() - t0 < timeout:
        esperar(app, 2.0)
        cmin = int(blk.count.min())
        print('[sim] t=%5.0fs  bits por punto (min) = %d / %d' % (time.time() - t0, cmin, meta))
        if not capt_media and cmin >= blk.bits_por_punto:
            capturar(tb, sinks, os.path.join(IMG, 'fase4'), 'sim_1barrido', app)
            capt_media = True
        if cmin >= meta:
            break
    esperar(app, 3.0)
    capturar(tb, sinks, os.path.join(IMG, 'fase4'), 'sim_final', app)
    tb.stop()
    tb.wait()
    try:
        print('[sim] saltos de 180 grados corregidos: %d, enganches: %d' % (tb.rx_ref.n_saltos, tb.rx_ref.n_locks))
    except Exception:
        pass
    # Resumen numerico directo del medidor
    print('[sim] Resumen del medidor e_BER_Curve:')
    print('      Eb/N0   errores      bits        BER')
    for eb, e, n in zip(blk.eb_axis, blk.errors, blk.count):
        print('      %5.1f %9d %9d   %.3e' % (eb, e, n, e / max(n, 1)))
    csv = os.path.join(BUILD, 'curva_BER_simulacion.csv')
    dst = os.path.join(RAIZ, 'resultados', 'simulacion', 'curva_BER_simulacion.csv')
    if os.path.exists(csv):
        shutil.copy2(csv, dst)
        print('[sim] CSV copiado ->', os.path.relpath(dst, RAIZ))
    with open(os.path.join(RAIZ, 'resultados', 'simulacion', 'conteos_simulacion.csv'), 'w') as f:
        f.write('EbN0_dB,errores,bits,BER\n')
        for eb, e, n in zip(blk.eb_axis, blk.errors, blk.count):
            f.write('%.1f,%d,%d,%.6e\n' % (eb, e, n, e / max(n, 1)))
    tb.close()


# ------------------------------------------------------------------ enlace en Python (sin GUI)
def enlace(nbits, ebn0=None, costas_bw=None, fll_bw=None, pfb_bw=None):
    """Mismo Tx + canal (CFO 300 Hz, 10 ppm, 0.7 rad) + receptor de SIM_LAZO_BPSK_BER.
    Si ebn0 no es None, inserta e_EbN0_Sweep fijo en ese valor (un solo punto).
    Devuelve (ref, rx, ber_monitor, bloque_ref)."""
    import numpy as np
    from gnuradio import gr, blocks, digital, analog, channels, filter
    from gnuradio.filter import firdes
    import math, cmath
    ins = os.path.join(RAIZ, 'grc', 'instrumentacion')
    if ins not in sys.path:
        sys.path.insert(0, ins)
    import e_PRBS15_Tx, e_Ref_PRBS15_Rx, e_EbN0_Sweep
    costas_bw = costas_bw or 2 * math.pi / 100
    fll_bw = fll_bw or 2 * math.pi / 400
    pfb_bw = pfb_bw or 2 * math.pi / 100
    Rs, Sps, beta, span, nfilts = 8000, 8, 0.5, 11, 32
    fs = Rs * Sps
    tb = gr.top_block()
    src = e_PRBS15_Tx.blk(32767)
    head = blocks.head(gr.sizeof_char, nbits)
    mapb = digital.chunks_to_symbols_bc([-1 + 0j, 1 + 0j], 1)
    rrc = filter.interp_fir_filter_ccf(Sps, firdes.root_raised_cosine(Sps, fs, Rs, beta, span * Sps))
    ch = channels.channel_model(0.0, 300 / fs, 1.0 + 10e-6, [0.3 * cmath.exp(0.7j)], 0)
    agc1 = analog.agc_cc(1e-3, 1.0, 1.0)
    agc1.set_max_gain(1000)
    fll = digital.fll_band_edge_cc(Sps, beta, 44, fll_bw)
    pfb = digital.pfb_clock_sync_ccf(Sps, pfb_bw,
                                     firdes.root_raised_cosine(nfilts, nfilts * Sps, 1.0, beta, span * Sps * nfilts),
                                     nfilts, nfilts / 2, 1.5, 1)
    agc2 = analog.agc_cc(1e-3, 1.0, 1.0)
    agc2.set_max_gain(100)
    costas = digital.costas_loop_cc(costas_bw, 2, False)
    const = digital.constellation_calcdist([-1 + 0j, 1 + 0j], [0, 1], 2, 1).base()
    dec = digital.constellation_decoder_cb(const)
    ref = e_Ref_PRBS15_Rx.blk(32767)
    sink_ref = blocks.vector_sink_b()
    sink_rx = blocks.vector_sink_b()
    sink_ber = blocks.vector_sink_f()
    if ebn0 is None:
        tb.connect(src, head, mapb, rrc, ch, agc1)
    else:
        sw = e_EbN0_Sweep.blk(EbN0_min=ebn0, EbN0_max=ebn0, EbN0_step=1.0, samp_rate=fs, bit_rate=Rs,
                              bits_por_punto=10 ** 9, bits_guardia=0, seed=2026)
        nul = blocks.null_sink(gr.sizeof_float)
        tb.connect(src, head, mapb, rrc, ch, sw, agc1)
        tb.connect((sw, 1), nul)
    tb.connect(agc1, fll, pfb, agc2, costas, dec, ref)
    tb.connect(dec, sink_rx)
    tb.connect((ref, 0), sink_ref)
    tb.connect((ref, 1), sink_ber)
    tb.run()
    return (np.array(sink_ref.data(), dtype=np.uint8), np.array(sink_rx.data(), dtype=np.uint8),
            np.array(sink_ber.data()), ref)


def paso_costas(nbits=150000):
    """Estudio del ancho de banda del lazo de Costas (y saltos de ciclo) a Eb/N0 bajos."""
    import math
    import numpy as np
    from math import erfc, sqrt
    filas = []
    print('[costas] costas_bw    Eb/N0   BER medida   BER teoria   saltos180  reenganches')
    for den in (100, 200, 400, 800):
        for eb in (0.0, 2.0, 4.0, 6.0):
            r, x, b, blk = enlace(nbits, ebn0=eb, costas_bw=2 * math.pi / den)
            i0 = 5000
            ber = np.count_nonzero(r[i0:] != x[i0:]) / max(len(r) - i0, 1)
            teo = 0.5 * erfc(sqrt(10 ** (eb / 10)))
            filas.append((den, eb, ber, teo, blk.n_saltos, blk.n_locks))
            print('[costas] 2pi/%-5d  %5.1f   %.3e    %.3e   %8d  %8d' % (den, eb, ber, teo, blk.n_saltos, blk.n_locks))
    with open(os.path.join(RAIZ, 'resultados', 'simulacion', 'estudio_costas.csv'), 'w') as f:
        f.write('costas_bw_den,EbN0_dB,BER,BER_teorica,saltos_180,enganches\n')
        for fila in filas:
            f.write('%d,%.1f,%.6e,%.6e,%d,%d\n' % fila)
    # mejor: menor suma de log10(BER/teoria) en los 4 puntos
    puntaje = {}
    for den, eb, ber, teo, ns, nl in filas:
        puntaje[den] = puntaje.get(den, 0.0) + math.log10(max(ber, 1e-7) / teo)
    mejor = min(puntaje, key=puntaje.get)
    print('[costas] puntaje (suma log10 BER/teoria):', {k: round(v, 3) for k, v in puntaje.items()})
    print('[costas] ELEGIDO costas_bw = 2*pi/%d' % mejor)
    with open(os.path.join(RAIZ, 'resultados', 'simulacion', 'costas_elegido.txt'), 'w') as f:
        f.write(str(mejor))


# ------------------------------------------------------------------ condicion limpia
def costas_den():
    ruta = os.path.join(RAIZ, 'resultados', 'simulacion', 'costas_elegido.txt')
    try:
        return int(open(ruta).read().strip())
    except Exception:
        return 100


def paso_limpio(nbits=200000):
    """Mismo Tx + canal + receptor de SIM_LAZO, SIN e_EbN0_Sweep: BER ~ 0."""
    import math
    import numpy as np
    r, x, b, blk = enlace(nbits, ebn0=None, costas_bw=2 * math.pi / costas_den())
    ok = np.where(b >= 0)[0]
    i0 = ok[0] if len(ok) else len(b)
    err = int(np.count_nonzero(r[i0:] != x[i0:]))
    tot = len(r) - i0
    print('[limpio] bits totales %d, enganche en el bit %d, bits comparados %d, errores %d, BER = %.2e'
          % (len(r), i0, tot, err, err / max(tot, 1)))
    if err == 0 and tot > 0:
        print('[limpio] Ningun error en %d bits: BER < 3/N = %.1e (95 %% de confianza)' % (tot, 3.0 / tot))
    with open(os.path.join(RAIZ, 'resultados', 'simulacion', 'condicion_limpia.txt'), 'w') as f:
        f.write('Prueba en condicion limpia (sin e_EbN0_Sweep): canal con CFO 300 Hz, 10 ppm, desfase 0.7 rad\n')
        f.write('bits_totales=%d\nbit_enganche=%d\nbits_comparados=%d\nerrores=%d\nBER=%.3e\ncota_3_sobre_N=%.3e\n'
                % (len(r), i0, tot, err, err / max(tot, 1), 3.0 / max(tot, 1)))


# ------------------------------------------------------------------ diagramas
def paso_diagramas():
    """PNG de cada flujograma usando la misma rutina de 'Screen Capture' de GRC."""
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import Gtk
    app = Gtk.Application(application_id='edu.uis.comii.captura')
    app.register(None)            # el lienzo de GRC espera una Gtk.Application por defecto
    from gnuradio import gr
    from gnuradio.grc.gui.Platform import Platform
    from gnuradio.grc.gui import Utils
    platform = Platform(version=gr.version(),
                        version_parts=(gr.major_version(), gr.api_version(), gr.minor_version()),
                        prefs=gr.prefs(), install_prefix=gr.prefix())
    platform.build_library()
    dest = os.path.join(IMG, 'flujogramas')
    os.makedirs(dest, exist_ok=True)
    for g in todos_los_grc():
        try:
            fg = platform.make_flow_graph(g)
            fg.rewrite()
            fg.validate()
            ruta = os.path.join(dest, os.path.basename(g).replace('.grc', '.png'))
            Utils.make_screenshot(fg, ruta, False)
            print('[diagrama]', os.path.relpath(ruta, RAIZ))
        except Exception:
            print('[diagrama] fallo en', os.path.basename(g))
            traceback.print_exc()


if __name__ == '__main__':
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    flog = open(LOG, 'a', encoding='utf-8')
    sys.stdout = Tee(sys.__stdout__, flog)
    sys.stderr = Tee(sys.__stderr__, flog)
    pasos = sys.argv[1:] or ['compilar', 'beta', 'costas', 'limpio', 'sim']
    print('=' * 70)
    print(time.strftime('%Y-%m-%d %H:%M:%S'), 'pasos:', pasos)
    from gnuradio import gr
    print('GNU Radio', gr.version(), '| Python', sys.version.split()[0])
    for p in pasos:
        try:
            {'compilar': paso_compilar, 'beta': paso_beta, 'sim': paso_sim, 'costas': paso_costas,
             'limpio': paso_limpio, 'diagramas': paso_diagramas}[p]()
        except Exception:
            print('[ERROR] en el paso', p)
            traceback.print_exc()
    print('FIN', time.strftime('%H:%M:%S'))
