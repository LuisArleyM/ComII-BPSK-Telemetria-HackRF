KIT BER PARA SISTEMAS SDR — COMUNICACIONES II

OBJETIVO
Añadir una medición de rendimiento BER vs Eb/N0 a los sistemas que los
estudiantes ya implementaron con USRP y/o HackRF One, sin reemplazar su
transmisor ni su receptor.

ARQUITECTURA RECOMENDADA

Tx bits -> Tx digital -> SDR Sink -> canal físico -> SDR Source
                                              |
                                              v
                                   Adaptación radio_rate -> bb_rate
                                              |
                                              v
                                      e_EbN0_Sweep
                                              |
                                              v
                                       Receptor digital
                                              |
                                              v
                                           Rx bits

Tx bits -------------------------------------> e_BER_Curve <----- Rx bits
                                                    |
                                                    v
                                         QT GUI Vector Sink
                                         log10(BER) vs Eb/N0

IMPORTANTE
1. e_EbN0_Sweep debe colocarse DESPUÉS de la adaptación a bb_rate y ANTES
   del receptor digital. El parámetro samp_rate del bloque debe ser esa bb_rate.
2. bit_rate debe ser la Rb real del sistema.
3. Los bits Tx y Rx deben ser bytes 0/1.
4. Para QPSK, 8PSK y QAM, la entrada Rx del medidor debe estar DESPUÉS
   del demapeo símbolo -> bits.
5. delay_bits compensa el retardo del receptor. Primero se calibra con una
   condición limpia hasta obtener BER aproximadamente cero.
6. EbN0_min, EbN0_max, EbN0_step, bits_por_punto y bits_guardia deben ser
   iguales en los dos Embedded Python Blocks.
7. Cada punto se mide durante bits_por_punto bits; el barrido se repite
   automáticamente y la curva continúa refinándose.
8. Con bits_por_punto=100000, un BER cercano a 1e-3 produce alrededor
   de 100 errores por visita al punto. Para estudiar BER menores deben
   aumentarse los bits por punto.
9. Si Tx y Rx están en computadores distintos, ambos deben conocer la misma
   secuencia binaria de prueba. La opción más sencilla es utilizar una secuencia
   PRBS o patrón periódico conocido y alinear la referencia en el receptor.
10. La curva obtenida es una caracterización HÍBRIDA: conserva las
    imperfecciones reales del frente SDR/enlace y añade AWGN digital controlado.
    Para que Eb/N0 sea reproducible, la primera prueba debe hacerse por cable,
    con atenuación adecuada y con una SNR física de base suficientemente alta.

PARÁMETROS INICIALES SUGERIDOS
EbN0_min       = 0 dB
EbN0_max       = 14 dB
EbN0_step      = 1 dB
bits_por_punto = 100000
bits_guardia   = 1000
update_every   = 1000
delay_bits     = ajustar experimentalmente
samp_rate      = bb_rate del receptor
bit_rate       = Rb del sistema

CURVA
Eje X: Eb/N0 [dB]
Eje Y: log10(BER)

El vector de salida 1 de e_BER_Curve es BER lineal.
El vector de salida 2 es log10(BER) y es el recomendado para la gráfica.

CRITERIO DEL PROYECTO
La comparación simulación/experimental se realizará a un mismo BER,
preferiblemente alrededor de BER=1e-3. La referencia acordada es considerar
conforme una penalización experimental no mayor a 2 dB, siempre que la
medición tenga suficiente soporte estadístico.
