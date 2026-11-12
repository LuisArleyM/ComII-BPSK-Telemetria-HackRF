"""
diagrama_grc.py
Dibuja el flujograma de cada .grc del proyecto a partir del propio archivo
(bloques y conexiones reales), con Graphviz. Resalta en naranja los bloques
del instrumento BER del curso, en azul los bloques propios del grupo y en
gris los bloques de hardware.

Uso:  python scripts/diagrama_grc.py      (requiere el programa 'dot' de Graphviz)
Salida: docs/img/flujogramas/<nombre>.png
"""
import glob
import os
import subprocess
import yaml

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OMITIR = ('variable', 'import', 'options')
INSTR = {'e_EbN0_Sweep', 'e_BER_Curve', 'e_BER_CSV', 'curva_ber'}
PROPIOS = {'tx_prbs', 'rx_ref', 'lat_comp'}
HW = ('osmosdr_source', 'osmosdr_sink')
CORTO = {
    'epy_block': 'Embedded Python', 'osmosdr_source': 'Osmocom Source', 'osmosdr_sink': 'Osmocom Sink',
    'rational_resampler_xxx': 'Rational Resampler', 'freq_xlating_fir_filter_xxx': 'Freq Xlating FIR',
    'analog_agc_xx': 'AGC', 'digital_fll_band_edge_cc': 'FLL Band-Edge',
    'digital_pfb_clock_sync_xxx': 'Polyphase Clock Sync', 'digital_costas_loop_cc': 'Costas Loop',
    'digital_constellation_decoder_cb': 'Constellation Decoder', 'blocks_delay': 'Delay',
    'qtgui_vector_sink_f': 'QT GUI Vector Sink', 'qtgui_const_sink_x': 'QT GUI Constellation',
    'qtgui_freq_sink_x': 'QT GUI Frequency', 'qtgui_time_sink_x': 'QT GUI Time',
    'qtgui_number_sink': 'QT GUI Number', 'blocks_null_sink': 'Null Sink',
    'blocks_multiply_const_vxx': 'Multiply Const', 'digital_chunks_to_symbols_xx': 'Chunks to Symbols',
    'interp_fir_filter_xxx': 'Interpolating FIR', 'analog_noise_source_x': 'Noise Source',
    'blocks_add_xx': 'Add', 'channels_channel_model': 'Channel Model', 'blocks_throttle': 'Throttle',
    'analog_random_source_x': 'Random Source', 'blocks_pack_k_bits_bb': 'Pack K Bits',
    'blocks_packed_to_unpacked_xx': 'Packed to Unpacked', 'blocks_vector_source_x': 'Vector Source',
    'blocks_complex_to_real': 'Complex to Real', 'blocks_repeat': 'Repeat',
    'analog_frequency_modulator_fc': 'Frequency Mod', 'analog_quadrature_demod_cf': 'Quadrature Demod',
}
CLAVES = {
    'rational_resampler_xxx': ('interp', 'decim'), 'freq_xlating_fir_filter_xxx': ('center_freq',),
    'osmosdr_source': ('freq0', 'sample_rate'), 'osmosdr_sink': ('freq0', 'sample_rate'),
    'blocks_delay': ('delay',), 'digital_costas_loop_cc': ('w',), 'blocks_multiply_const_vxx': ('const',),
    'interp_fir_filter_xxx': ('interp',), 'analog_noise_source_x': ('amp',),
    'blocks_vector_source_x': ('vector',),
}


def dibujar(grc):
    d = yaml.safe_load(open(grc, encoding='utf-8'))
    bloques = {b['name']: b for b in d['blocks']
               if not b['id'].startswith(OMITIR) and b['states'].get('state', 'enabled') not in ('disabled', False)}
    lineas = ['digraph G {',
              '  graph [rankdir=LR, bgcolor="#fcfcfb", pad=0.3, nodesep=0.2, ranksep=0.4, fontname="Helvetica",'
              ' label="%s", labelloc=t, fontsize=16];' % os.path.basename(grc),
              '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#52514e",'
              ' fillcolor="#ffffff", penwidth=1.1];',
              '  edge [color="#52514e", arrowsize=0.6, fontname="Helvetica", fontsize=8, fontcolor="#52514e"];']
    for n, b in bloques.items():
        tipo = CORTO.get(b['id'], b['id'])
        extra = ''
        for k in CLAVES.get(b['id'], ()):
            v = str(b['parameters'].get(k, ''))
            if len(v) > 28:
                v = v[:25] + '...'
            extra += '\\n%s = %s' % (k, v.replace('"', "'"))
        estilo = ''
        if n in INSTR:
            estilo = ', fillcolor="#fde4d9", color="#eb6834", penwidth=2'
        elif n in PROPIOS:
            estilo = ', fillcolor="#dbe9fa", color="#2a78d6", penwidth=1.6'
        elif b['id'] in HW:
            estilo = ', fillcolor="#e6e5e1"'
        elif b['id'].startswith('qtgui') or b['id'] == 'blocks_null_sink':
            estilo = ', fillcolor="#f3f2ef", fontcolor="#52514e"'
        lineas.append('  "%s" [label="%s\\n(%s)%s"%s];' % (n, n, tipo, extra, estilo))
    for a, pa, bb, pb in d['connections']:
        if a in bloques and bb in bloques:
            lab = '' if (str(pa), str(pb)) == ('0', '0') and bb != 'e_BER_Curve' else ' [label="%s→%s"]' % (pa, pb)
            lineas.append('  "%s" -> "%s"%s;' % (a, bb, lab))
    lineas.append('}')
    dest = os.path.join(RAIZ, 'docs', 'img', 'flujogramas')
    os.makedirs(dest, exist_ok=True)
    png = os.path.join(dest, os.path.basename(grc).replace('.grc', '.png'))
    subprocess.run(['dot', '-Tpng', '-Gdpi=110', '-o', png], input='\n'.join(lineas).encode('utf-8'), check=True)
    print('->', os.path.relpath(png, RAIZ))


if __name__ == '__main__':
    for g in sorted(glob.glob(os.path.join(RAIZ, 'grc', 'fase*', '*.grc'))):
        dibujar(g)
