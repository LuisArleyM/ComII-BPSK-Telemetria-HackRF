"""
analizar_curva_BER.py
Grafica y compara las curvas BER vs Eb/N0 del proyecto:
  * teoria BPSK en AWGN: Pb = Q(sqrt(2 Eb/N0)) = 0.5 erfc(sqrt(Eb/N0))
  * simulacion GNU Radio en lazo (resultados/simulacion/curva_BER_simulacion.csv)
  * medicion con HackRF (resultados/experimental/curva_BER.csv), si ya existe

Para cada curva calcula el Eb/N0 necesario para BER = 1e-3 (interpolando
log10(BER) entre los dos puntos medidos que encierran -3) y la penalizacion
respecto a la teoria y a la simulacion. Criterio del proyecto: penalizacion
experimental <= 2 dB a BER = 1e-3.

Los puntos sin errores NO se dibujan como BER = 0: el CSV trae log10(3/N),
que es una cota superior (95 %) y se dibuja con marcador hueco.

Uso:  python scripts/analizar_curva_BER.py
Salidas: docs/img/fase4/curva_BER_comparacion.png y resultados/resumen_BER.md
"""
import csv
import os
import numpy as np
from math import erfc, sqrt

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CURVAS = [
    ('Simulación GNU Radio (lazo, CFO + error de reloj)',
     os.path.join(RAIZ, 'resultados', 'simulacion', 'curva_BER_simulacion.csv'), '#2a78d6'),
    ('Experimental HackRF One',
     os.path.join(RAIZ, 'resultados', 'experimental', 'curva_BER.csv'), '#eb6834'),
]
OBJ = 1e-3


def teoria(eb_db):
    return np.array([0.5 * erfc(sqrt(10 ** (e / 10.0))) for e in np.atleast_1d(eb_db)])


def leer(ruta):
    eb, ber, lb = [], [], []
    with open(ruta, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            eb.append(float(r['EbN0_dB']))
            ber.append(float(r['BER']))
            lb.append(float(r['log10_BER']))
    return np.array(eb), np.array(ber), np.array(lb)


def ebn0_en(eb, ber, objetivo=OBJ):
    """Eb/N0 [dB] donde la curva cruza 'objetivo' (interpolacion en log10)."""
    y = np.log10(objetivo)
    for i in range(len(eb) - 1):
        if ber[i] > 0 and ber[i + 1] > 0:
            a, b = np.log10(ber[i]), np.log10(ber[i + 1])
            if (a - y) * (b - y) <= 0 and a != b:
                return eb[i] + (y - a) * (eb[i + 1] - eb[i]) / (b - a)
    return None


def ebn0_teorico(objetivo=OBJ):
    lo, hi = 0.0, 20.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if teoria(m)[0] > objetivo:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#52514e', 'xtick.color': '#52514e',
                         'ytick.color': '#52514e'})
    e_teo = ebn0_teorico()
    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=150)
    x = np.linspace(0, 14, 300)
    ax.semilogy(x, teoria(x), '--', color='#52514e', lw=2, label='Teoría BPSK: Q(√(2Eb/N0))')
    lineas = ['| Curva | Eb/N0 para BER = 1e-3 | Penalización vs teoría |',
              '|---|---|---|',
              '| Teoría BPSK (AWGN) | %.2f dB | 0 dB |' % e_teo]
    resultados = {}
    for nombre, ruta, color in CURVAS:
        if not os.path.exists(ruta):
            lineas.append('| %s | pendiente (falta %s) | - |' % (nombre, os.path.relpath(ruta, RAIZ)))
            continue
        eb, ber, lb = leer(ruta)
        con = ber > 0
        ax.semilogy(eb[con], ber[con], 'o-', color=color, lw=2, ms=7, mec='#fcfcfb', mew=1.5, label=nombre)
        if np.any(~con):
            ax.semilogy(eb[~con], 10 ** lb[~con], 'v', color=color, mfc='none', ms=8, mew=1.5,
                        label='%s: sin errores (cota 3/N)' % nombre.split(' (')[0])
        e = ebn0_en(eb, ber)
        resultados[nombre] = e
        lineas.append('| %s | %s | %s |' % (nombre, '%.2f dB' % e if e is not None else 'no cruza 1e-3',
                                             '%+.2f dB' % (e - e_teo) if e is not None else '-'))
    ax.axhline(OBJ, color='#b9b8b3', lw=1)
    ax.text(0.2, OBJ * 1.25, 'BER = 1e-3 (criterio de comparación)', color='#52514e', fontsize=9)
    ax.set_xlabel('Eb/N0 [dB]')
    ax.set_ylabel('BER')
    ax.set_xlim(0, 14)
    ax.set_ylim(1e-7, 0.5)
    ax.grid(True, which='major', color='#e4e3df', lw=0.8)
    ax.set_title('BPSK, Rb = 8 kb/s: BER vs Eb/N0', loc='left', fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc='lower left')
    fig.tight_layout()
    ruta_fig = os.path.join(RAIZ, 'docs', 'img', 'fase4', 'curva_BER_comparacion.png')
    os.makedirs(os.path.dirname(ruta_fig), exist_ok=True)
    fig.savefig(ruta_fig, facecolor='#fcfcfb')
    sim = resultados.get(CURVAS[0][0])
    exp = resultados.get(CURVAS[1][0])
    if sim is not None and exp is not None:
        pen = exp - sim
        lineas.append('')
        lineas.append('Penalización experimental respecto a la simulación a BER = 1e-3: **%+.2f dB** (%s el criterio de 2 dB).'
                      % (pen, 'cumple' if pen <= 2.0 else 'NO cumple'))
    with open(os.path.join(RAIZ, 'resultados', 'resumen_BER.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lineas) + '\n')
    print('\n'.join(lineas))
    print('figura ->', os.path.relpath(ruta_fig, RAIZ))


if __name__ == '__main__':
    main()
