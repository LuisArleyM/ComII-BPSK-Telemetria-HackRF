"""
analisis_impulsivo.py  (extension de la fase beta, escenario S1)

Modelo numerico (numpy) del mismo enlace del GRC Enlace_Beta_Impulsivo_*.grc:
    Rs = 32 kbaud, Sps = 8, fs = 256 kS/s, pulso rectangular,
    ruido complejo noise_amp = 0.10 (potencia total 0.01),
    impulso real A cada 256 muestras (A = 0, 0.3, 0.6, 1.0).

Calcula, para cada nivel de la tabla de pruebas obligatorias:
  * subida del piso de la PSD (ruido + tren de impulsos) respecto a la referencia,
  * BER BPSK con decision sobre UNA muestra por simbolo (sin filtro), en el peor
    caso en que el instante de muestreo coincide con el impulso,
  * BER BPSK con filtro acoplado (integrar y descargar sobre Sps muestras),
  * BER BFSK con discriminador (media de la frecuencia instantanea en el simbolo).

Uso:  python scripts/analisis_impulsivo.py
Salidas: resultados/simulacion/analisis_impulsivo.csv y docs/img/fase2/efecto_filtro_acoplado.png
"""
import os
import numpy as np

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
Rs, Sps = 32000, 8
fs = Rs * Sps
NIMP = 256
NOISE = 0.10
NIVELES = [('Referencia', 0.0), ('Suave', 0.3), ('Media', 0.6), ('Fuerte', 1.0)]
NSYM = 2_000_000
rng = np.random.default_rng(2026)


def ruido(n):
    return (rng.standard_normal(n) + 1j * rng.standard_normal(n)) * NOISE / np.sqrt(2)


def tren(n, A, fase):
    x = np.zeros(n, complex)
    x[fase::NIMP] = A
    return x


def ber_bpsk(A):
    bits = rng.integers(0, 2, NSYM)
    s = np.repeat(2.0 * bits - 1.0, Sps)
    fase_imp = 3                     # posicion del impulso dentro del simbolo
    r = s + ruido(len(s)) + tren(len(s), A, fase_imp)
    R = r.reshape(-1, Sps)
    una = (R[:, fase_imp].real > 0).astype(int)        # muestreo justo en el impulso (peor caso)
    mf = (R.mean(axis=1).real > 0).astype(int)          # integrar y descargar
    return np.mean(una != bits), np.mean(mf != bits)


def ber_bfsk(A, desv=16000.0):
    nsym = NSYM // 4
    bits = rng.integers(0, 2, nsym)
    f = np.repeat(2.0 * bits - 1.0, Sps) * desv
    fase = 2 * np.pi * np.cumsum(f) / fs
    s = np.exp(1j * fase)
    r = s + ruido(len(s)) + tren(len(s), A, 3)
    fi = np.angle(r[1:] * np.conj(r[:-1])) * fs / (2 * np.pi * desv)
    fi = np.concatenate(([0.0], fi))
    F = fi.reshape(-1, Sps)
    dec = (F[:, 1:].mean(axis=1) > 0).astype(int)
    # Magnitud tipica del 'chasquido' en la frecuencia instantanea: maximo de
    # |f_inst| en la muestra del impulso y la siguiente (mediana sobre impulsos).
    idx = np.arange(3, len(fi) - 1, NIMP)
    pico = np.median(np.maximum(np.abs(fi[idx]), np.abs(fi[idx + 1])))
    return np.mean(dec != bits), pico


def piso_psd(A, nfft=1024, nprom=400):
    n = nfft * nprom
    x = ruido(n) + tren(n, A, 3)
    w = np.blackman(nfft)
    X = np.fft.fft(x.reshape(nprom, nfft) * w, axis=1)
    return np.mean(np.abs(X) ** 2)


def main():
    filas = []
    p0 = piso_psd(0.0)
    print('Nivel       A    piso PSD [dB]  BER BPSK 1 muestra  BER BPSK filtro acoplado  BER BFSK  pico f_inst')
    for nombre, A in NIVELES:
        dp = 10 * np.log10(piso_psd(A) / p0)
        b1, bmf = ber_bpsk(A)
        bf, pico = ber_bfsk(A)
        filas.append((nombre, A, dp, b1, bmf, bf, pico))
        print('%-10s %4.1f   %+6.2f         %9.2e           %9.2e            %9.2e   %5.2f'
              % (nombre, A, dp, b1, bmf, bf, pico))
    teo = [10 * np.log10(1 + A ** 2 / NIMP / NOISE ** 2) for _, A in NIVELES]
    print('Subida teorica del piso (ruido + potencia media del tren):', ['%+.2f dB' % t for t in teo])
    os.makedirs(os.path.join(RAIZ, 'resultados', 'simulacion'), exist_ok=True)
    with open(os.path.join(RAIZ, 'resultados', 'simulacion', 'analisis_impulsivo.csv'), 'w') as f:
        f.write('nivel,A_imp,subida_piso_dB,subida_piso_teorica_dB,BER_BPSK_una_muestra,'
                'BER_BPSK_filtro_acoplado,BER_BFSK_discriminador,chasquido_frec_inst_mediana_norm\n')
        for (nombre, A, dp, b1, bmf, bf, pico), t in zip(filas, teo):
            f.write('%s,%.1f,%.3f,%.3f,%.3e,%.3e,%.3e,%.3f\n' % (nombre, A, dp, t, b1, bmf, bf, pico))
    figura()


def figura():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#52514e', 'axes.labelcolor': '#0b0b0b',
                         'xtick.color': '#52514e', 'ytick.color': '#52514e'})
    A = 1.0
    bits = np.array([0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1])
    s = np.repeat(2.0 * bits - 1.0, Sps)
    r = s.astype(complex).copy()
    r[3::NIMP] += A              # un impulso en la muestra 3 (simbolo 0)
    r[3 + 5 * Sps] += A          # y otro sobre el simbolo 5 (bit 0) solo para ilustrar
    t = np.arange(len(r)) / fs * 1e6
    mf = r.real.reshape(-1, Sps).mean(axis=1)
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=150)
    ax.axhline(0, color='#b9b8b3', lw=1)
    ax.step(t, r.real, where='post', color='#2a78d6', lw=2, label='Muestras recibidas (sin filtro)')
    ts = (np.arange(len(bits)) + 0.5) * Sps / fs * 1e6
    ax.plot(ts, mf, 'o', ms=8, color='#eb6834', mec='#fcfcfb', mew=2,
            label='Salida del filtro acoplado (1 valor por símbolo)')
    for k in (0, 5):
        ax.annotate('impulso A = 1.0', xy=(t[3 + k * Sps], r.real[3 + k * Sps]),
                    xytext=(t[3 + k * Sps] + 6, 1.75), color='#52514e', fontsize=9,
                    arrowprops=dict(arrowstyle='-', color='#52514e', lw=1))
    ax.set_xlabel('Tiempo [µs]')
    ax.set_ylabel('Parte real')
    ax.set_ylim(-1.6, 2.3)
    ax.set_title('Un impulso de 1 muestra se reduce a A/Sps = 0.125 después del filtro acoplado',
                 loc='left', fontsize=11, color='#0b0b0b')
    ax.legend(loc='upper right', frameon=False, fontsize=9)
    ax.grid(axis='y', color='#e4e3df', lw=0.8)
    fig.tight_layout()
    ruta = os.path.join(RAIZ, 'docs', 'img', 'fase2', 'efecto_filtro_acoplado.png')
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    fig.savefig(ruta, facecolor='#fcfcfb')
    print('figura ->', ruta)


if __name__ == '__main__':
    main()
