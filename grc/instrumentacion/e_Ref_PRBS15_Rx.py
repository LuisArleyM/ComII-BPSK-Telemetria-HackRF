"""
e_Ref_PRBS15_Rx
Regenera en el RECEPTOR la secuencia de bits transmitida (PRBS-15) y la
alinea automaticamente con los bits recuperados.

Entrada 0 : bits recuperados por el receptor (byte 0/1), despues de la
            decision BPSK.
Salida 0  : bits Tx de referencia regenerados y alineados (byte 0/1).
            -> se conecta a la entrada 0 de e_BER_Curve.
Salida 1  : BER acumulada desde el ultimo enganche (float).
            -1 mientras no hay enganche. Sirve como evidencia de la
            condicion limpia (BER ~ 0) sin barrido de ruido.

Por que hace falta (Guia 4, "Tx y Rx en computadores diferentes"):
    Con Tx y Rx en computadores distintos, el instante en que arranca cada
    flujograma es arbitrario, por lo que el retardo Tx->Rx expresado en bits
    cambia en cada ejecucion. Un delay_bits fijo no sirve. Este bloque hace
    la misma tarea que ajustar delay_bits, pero de forma automatica:

    1) Adquisicion: toma los ultimos W bits recibidos y calcula su
       correlacion circular con la PRBS-15 completa (FFT). El maximo de
       |correlacion| da la fase de la secuencia y su signo da la polaridad
       (BPSK tiene ambiguedad de 180 grados: el lazo de Costas puede
       engancharse invertido y entregar todos los bits negados).
       Se acepta el enganche si las discrepancias son <= thr_acq*W.
       Con W=256 y thr_acq=0.25: P(falso enganche) ~ 1e-11 y
       P(no enganchar con BER real 15 %) ~ 1e-5.
    2) Seguimiento: genera la referencia continuando la fase hallada,
       independiente de los bits recibidos (los errores se cuentan de
       verdad, no se "corrigen").
    3) Saltos de ciclo de 180 grados: a baja Eb/N0 el lazo de Costas puede
       saltar media vuelta y desde ese instante TODOS los bits salen
       invertidos. Si en los ultimos Np = 32 bits hay al menos 75 % de
       discrepancias (imposible por ruido: con BER real de 15 % la
       probabilidad es ~1e-12), se invierte la polaridad de la referencia.
       Cada salto cuesta ~25 bits erroneos, que SI se cuentan; es el mismo
       efecto que tendria un sistema real que resuelve la ambiguedad con
       una secuencia conocida. Los saltos se cuentan en self.n_saltos.
    4) Perdida: si en una ventana de D bits la tasa de discrepancia supera
       thr_loss (35 %) con la polaridad ya corregida (deslizamiento de reloj:
       se gano o se perdio un bit), se vuelve a adquirir. Mientras tanto la
       referencia sigue la fase anterior, de modo que los bits de ese
       intervalo cuentan como errores reales.

    Antes del primer enganche la salida es el complemento de los bits
    recibidos (BER = 1): si no hay senal, la curva lo muestra en vez de
    aparentar BER = 0.

    Al engancharse imprime el retardo equivalente en bits (lo que habria que
    poner en delay_bits si el Tx empezara en el mismo instante que el Rx) y
    la polaridad detectada.

La salida 0 es 1:1 con la entrada (sync_block), por lo que el conteo de bits
de e_BER_Curve y la segmentacion del barrido de e_EbN0_Sweep no se alteran.
"""

import numpy as np
from gnuradio import gr


def prbs15(seed=0x7FFF):
    """Mismo generador que e_PRBS15_Tx (x^15 + x^14 + 1)."""
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
    def __init__(self, seed=32767, W=256, thr_acq=0.25, D=512, thr_loss=0.35, Np=32, thr_pol=0.75):
        gr.sync_block.__init__(
            self,
            name='e_Ref_PRBS15_Rx',
            in_sig=[np.uint8],
            out_sig=[np.uint8, np.float32]
        )
        self.seq = prbs15(int(seed))
        self.L = len(self.seq)
        self.W = int(W)
        self.thr_acq = float(thr_acq)
        self.D = int(D)
        self.thr_loss = float(thr_loss)
        self.Np = int(Np)
        self.thr_pol_n = int(np.ceil(float(thr_pol) * self.Np))
        self.pbuf = np.zeros(self.Np, dtype=np.int8)   # ventana circular de errores
        self.pidx = 0
        self.psum = 0
        self.pcnt = 0
        self.n_saltos = 0

        # FFT conjugada de la PRBS en +-1 para la correlacion circular.
        seq_pm = 1.0 - 2.0 * self.seq.astype(np.float64)
        self.F_seq = np.fft.fft(seq_pm)

        self.locked = False
        self.ever_locked = False
        self.phase = 0          # indice de la PRBS que corresponde al proximo bit
        self.inv = 0            # 1 si el receptor entrega los bits invertidos
        self.hist = np.zeros(0, dtype=np.uint8)
        self.nrx = 0            # bits recibidos desde el arranque
        self.win_err = 0
        self.win_cnt = 0
        self.err_lock = 0       # errores desde el ultimo enganche
        self.cnt_lock = 0
        self.n_locks = 0
        self.ber_out = -1.0

    # ------------------------------------------------------------------
    def _acquire(self, window):
        W = len(window)
        w_pm = np.zeros(self.L, dtype=np.float64)
        w_pm[:W] = 1.0 - 2.0 * window.astype(np.float64)
        # corr[p] = sum_k seq_pm[(p+k) % L] * w_pm[k]
        corr = np.real(np.fft.ifft(self.F_seq * np.conj(np.fft.fft(w_pm))))
        p0 = int(np.argmax(np.abs(corr)))
        c = corr[p0]
        mism = int(round((W - abs(c)) / 2.0))
        if mism <= self.thr_acq * W:
            inv = 1 if c < 0 else 0
            return True, (p0 + W) % self.L, inv, mism
        return False, 0, 0, mism

    def _reset_pol(self):
        self.pbuf[:] = 0
        self.pidx = 0
        self.psum = 0
        self.pcnt = 0

    def _seguir_polaridad(self, base, rx):
        """Referencia = base XOR polaridad, invirtiendo la polaridad cuando en
        los ultimos Np bits hay >= thr_pol*Np discrepancias (salto de 180 grados)."""
        ref = base ^ self.inv
        if self.Np <= 0:
            return ref
        err = (ref != rx).astype(np.int8)
        Np, thr = self.Np, self.thr_pol_n
        # Camino rapido (casi siempre): ni sumando todo el bloque se llega al umbral.
        if int(err.sum()) + self.psum < thr:
            if len(err) >= Np:
                self.pbuf[:] = err[-Np:]
                self.pidx = 0
                self.psum = int(self.pbuf.sum())
                self.pcnt = Np
            else:
                for e in err.tolist():
                    self.psum += e - int(self.pbuf[self.pidx])
                    self.pbuf[self.pidx] = e
                    self.pidx = (self.pidx + 1) % Np
                    self.pcnt = min(self.pcnt + 1, Np)
            return ref
        # Camino lento: bit a bit, con posible inversion de polaridad.
        buf = self.pbuf
        pidx, psum, pcnt, inv = self.pidx, self.psum, self.pcnt, self.inv
        b = base.tolist()
        r = rx.tolist()
        out = np.empty(len(b), dtype=np.uint8)
        for i in range(len(b)):
            e = 1 if (b[i] ^ inv) != r[i] else 0
            psum += e - int(buf[pidx])
            buf[pidx] = e
            pidx = (pidx + 1) % Np
            if pcnt < Np:
                pcnt += 1
            if pcnt == Np and psum >= thr:
                inv ^= 1
                self.n_saltos += 1
                buf[:] = 0
                psum = 0
                pcnt = 0
            out[i] = b[i] ^ inv
        self.pidx, self.psum, self.pcnt, self.inv = pidx, psum, pcnt, inv
        return out

    def work(self, input_items, output_items):
        rx_all = np.asarray(input_items[0], dtype=np.uint8) & 1
        out_ref = output_items[0]
        out_ber = output_items[1]
        n = min(len(rx_all), len(out_ref), len(out_ber))
        if n <= 0:
            return 0

        pos = 0
        while pos < n:
            if self.locked:
                # Seguimiento, en sub-bloques que terminan en la frontera de
                # la ventana de deteccion de perdida (D bits).
                m = min(n - pos, self.D - self.win_cnt)
                idx = (self.phase + np.arange(m, dtype=np.int64)) % self.L
                rx = rx_all[pos:pos + m]
                ref = self._seguir_polaridad(self.seq[idx], rx)
                out_ref[pos:pos + m] = ref
                err = int(np.count_nonzero(ref != rx))
                self.err_lock += err
                self.cnt_lock += m
                self.win_err += err
                self.win_cnt += m
                self.phase = int((self.phase + m) % self.L)
                self.nrx += m
                self.ber_out = self.err_lock / float(max(self.cnt_lock, 1))
                out_ber[pos:pos + m] = self.ber_out
                pos += m
                if self.win_cnt >= self.D:
                    if self.win_err > self.thr_loss * self.win_cnt:
                        self.locked = False
                        self.hist = np.zeros(0, dtype=np.uint8)
                        print('[RX-REF] Perdida de alineacion (%.0f %% de discrepancia en %d bits). '
                              'Re-adquiriendo...' % (100.0 * self.win_err / self.win_cnt, self.win_cnt))
                    self.win_err = 0
                    self.win_cnt = 0
            else:
                # Sin enganche: se intenta adquirir cada W/2 bits nuevos.
                if len(self.hist) < self.W:
                    m = min(n - pos, self.W - len(self.hist))
                else:
                    m = min(n - pos, max(1, self.W // 2))
                rx = rx_all[pos:pos + m]
                idx = (self.phase + np.arange(m, dtype=np.int64)) % self.L
                if self.ever_locked:
                    ref = self.seq[idx] ^ self.inv   # se cuentan errores reales
                else:
                    ref = rx ^ 1                     # sin senal: BER = 1
                out_ref[pos:pos + m] = ref
                out_ber[pos:pos + m] = self.ber_out
                self.phase = int((self.phase + m) % self.L)
                self.nrx += m
                self.hist = np.concatenate((self.hist, rx))[-self.W:]
                pos += m
                if len(self.hist) >= self.W:
                    ok, p_next, inv, mism = self._acquire(self.hist)
                    if ok:
                        self.locked = True
                        self.ever_locked = True
                        self.phase = p_next
                        self.inv = inv
                        self.err_lock = 0
                        self.cnt_lock = 0
                        self.win_err = 0
                        self.win_cnt = 0
                        self.n_locks += 1
                        self._reset_pol()
                        # Corrige hacia atras la referencia de los bits de la
                        # ventana que aun pertenecen a esta llamada.
                        a = max(0, pos - self.W)
                        k = pos - a
                        back = (p_next - k + np.arange(k, dtype=np.int64)) % self.L
                        out_ref[a:pos] = self.seq[back] ^ inv
                        delay = int((self.nrx - self.phase) % self.L)
                        print('[RX-REF] Enganche #%d: %d/%d discrepancias en la ventana, '
                              'polaridad %s, retardo equivalente = %d bits (mod %d).'
                              % (self.n_locks, mism, self.W,
                                 'INVERTIDA (180 grados)' if inv else 'normal',
                                 delay, self.L))
                        self.hist = np.zeros(0, dtype=np.uint8)
        return n
