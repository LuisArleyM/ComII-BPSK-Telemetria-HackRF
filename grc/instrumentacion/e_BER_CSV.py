import numpy as np
from gnuradio import gr
from pathlib import Path
import csv
import time


class blk(gr.sync_block):

    def __init__(self,
                 EbN0_min=0.0,
                 EbN0_max=14.0,
                 EbN0_step=1.0,
                 nombre_archivo="curva_BER.csv",
                 guardar_cada=2.0):

        self.EbN0_min = float(EbN0_min)
        self.EbN0_max = float(EbN0_max)
        self.EbN0_step = float(EbN0_step)

        self.N = int(round(
            (self.EbN0_max - self.EbN0_min) /
            self.EbN0_step
        )) + 1

        gr.sync_block.__init__(
            self,
            name='Guardar curva BER en CSV',
            in_sig=[
                (np.float32, self.N),
                (np.float32, self.N)
            ],
            out_sig=None
        )

        self.nombre_archivo = str(nombre_archivo)
        self.guardar_cada = float(guardar_cada)

        # El Embedded Python Block se genera junto al flowgraph de GNU Radio.
        # Por ello el CSV queda en la misma carpeta contenedora del .grc/.py.
        # NOTA DE COMPATIBILIDAD (grupo): GRC ejecuta este codigo sin __file__ al
        # cargar el .grc ("name '__file__' is not defined"). En ejecucion normal
        # __file__ existe y el CSV queda junto al .py generado, como se pretendia.
        try:
            self.carpeta = Path(__file__).resolve().parent
        except NameError:
            self.carpeta = Path.cwd()
        self.ruta_csv = self.carpeta / self.nombre_archivo

        self.ultimo_guardado = 0.0
        self.ebn0 = self.EbN0_min + self.EbN0_step * np.arange(self.N)

        print("CSV BER se guardará en:")
        print(self.ruta_csv)

    def guardar(self, ber, logber):
        archivo_temporal = self.ruta_csv.with_suffix(".tmp")

        with open(archivo_temporal, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["EbN0_dB", "BER", "log10_BER"])

            for eb, b, lb in zip(self.ebn0, ber, logber):
                writer.writerow([
                    f"{eb:.6f}",
                    f"{float(b):.12e}",
                    f"{float(lb):.12e}"
                ])

        archivo_temporal.replace(self.ruta_csv)

    def work(self, input_items, output_items):
        ber_vectors = input_items[0]
        log_vectors = input_items[1]

        if len(ber_vectors) == 0:
            return 0

        ahora = time.time()
        if ahora - self.ultimo_guardado >= self.guardar_cada:
            self.guardar(ber_vectors[-1], log_vectors[-1])
            self.ultimo_guardado = ahora

        return len(ber_vectors)
