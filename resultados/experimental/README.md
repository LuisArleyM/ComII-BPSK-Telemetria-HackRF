# Resultados experimentales (HackRF One)

Aquí va el archivo **`curva_BER.csv` generado automáticamente** por `e_BER_CSV` al ejecutar
`grc/fase4_ber/LAB_RX_BPSK_HackRF_BER.grc` con los dos HackRF One conectados por cable y atenuadores.

- Copiarlo tal como lo escribe GNU Radio (queda en la carpeta del flujograma). **No editar sus valores.**
- Junto al CSV, guardar: la captura de la condición limpia (`LAB_RX_BPSK_HackRF.grc`), la captura de la curva en
  el Vector Sink, el offset que muestra la FLL y las ganancias usadas (`tx_vga`, `rx_lna`, `rx_vga`, atenuación).
- Después ejecutar `python scripts/analizar_curva_BER.py` para obtener la comparación con la teoría y con la
  simulación, y la penalización a BER = 1e-3.

Estado: **pendiente de la sesión de laboratorio.**
