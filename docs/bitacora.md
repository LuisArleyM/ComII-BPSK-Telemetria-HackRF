---
title: Bitácora
---

[← Inicio](index.md) · [1. Escenario](01-escenario-beta.md) · [2. HackRF](02-hackrf.md) · [3. BER](03-ber.md) · **Bitácora**

# Bitácora del proyecto

Registro breve de lo realizado, las decisiones y los problemas. Las entradas de laboratorio se completan el día de la medición.

| Fecha | Actividad | Resultado / decisión |
|---|---|---|
| Fase beta | Selección del escenario en el selector guiado: **S1 telemetría industrial, BPSK, prueba principal media** | Valores base Rs = 32 kbaud, Sps = 8, fs = 256 kS/s, `noise_amp` = 0.10; solo se varía la amplitud del impulso |
| Sesión de clase (Fase 3) | Simulación del transmisor BPSK de laboratorio en GNU Radio | Capturas de la envolvente (solo I), PSD de ±6 kHz y plano I-Q real con Rs = 8 kbaud, β = 0.5, `tx_amp` = 0.15, `tx_vga` = 20 |
| 05/11/2026 | Sesión de laboratorio: enlace 16-QAM por aire entre dos HackRF One con los flujogramas del curso (fotos y video en la [fase 3](02-hackrf.md)) | Con las placas separadas, constelación irreconocible y `CRC=ERROR`; al acercarlas, 16 grupos y mensaje correcto. En régimen, 450 tramas seguidas verificadas (EVM ≈ 4.6 %). El espectro confirmó el LO desplazado ±200 kHz |
| 12/11/2026 | Construcción de `Enlace_Beta_Impulsivo_BPSK.grc` y de su versión BFSK; cuatro pruebas (0 / 0.3 / 0.6 / 1.0) ejecutadas en GNU Radio 3.10.12 | Capturas de tiempo, PSD y constelación. El impulso es claro en el tiempo, apenas visible en la PSD (+0.15 a +1.4 dB) |
| 12/11/2026 | Análisis numérico del efecto del impulso | Con una muestra por símbolo, BER = 7.8·10⁻³ con A = 1.0; con filtro acoplado, 0 errores en todos los niveles |
| 12/11/2026 | Adaptación de los flujogramas de laboratorio (16-QAM de referencia) a BPSK: `LAB_TX_BPSK_HackRF.grc`, `LAB_RX_BPSK_HackRF.grc` | Compilan con `grcc` sin errores. Fuente PRBS-15 en el Tx para tener una secuencia conocida en ambos PC |
| 12/11/2026 | Diseño de `e_Ref_PRBS15_Rx` (referencia alineada por correlación) | Resuelve el retardo aleatorio entre PC y la ambigüedad de 180° del lazo de Costas |
| 12/11/2026 | Validación numérica del instrumento BER con receptor ideal | Coincide con Q(√(2Eb/N0)). Se descubrió un piso falso de 1.5·10⁻⁵ en 14 dB causado por la latencia del receptor; corregido con `lat_comp_bits` = 400 |
| 12/11/2026 | Integración de `e_EbN0_Sweep` y `e_BER_Curve` (`LAB_RX_BPSK_HackRF_BER.grc`, `SIM_LAZO_BPSK_BER.grc`) | `e_BER_Curve` y `e_BER_CSV` no cargaban en GNU Radio 3.10.12: se corrigió la clase base (`gr.decim_block`) y el uso de `__file__`, sin cambiar el algoritmo |
| 12/11/2026 | Prueba en condición limpia (simulación con CFO 300 Hz, 10 ppm, 0.7 rad) | Retardo equivalente 18 bits; con los lazos finales, enganche en el bit 1024 y **0 errores en 198 882 bits** |
| 12/11/2026 | Primera curva BER simulada con el receptor completo (FLL 2π/400, Costas 2π/100) | BER de 35 % en 0 dB: cientos de saltos de 180° del lazo de Costas |
| 12/11/2026 | Seguimiento de polaridad en `e_Ref_PRBS15_Rx` | Cada salto cuesta ≈ 20 bits; BER en 0 dB baja a 22 %, pero siguen 3201 saltos |
| 12/11/2026 | Estudio de anchos de banda (4 valores de Costas y luego 3 × 3 FLL–Costas) | La causa era la FLL: con FLL 2π/2500 y Costas 2π/200 no hay saltos |
| 12/11/2026 | Curva BER simulada final (6 barridos, 9.1 M bits) | 6.91 dB a BER = 10⁻³ (0.12 dB sobre la teoría); sin errores en 11–14 dB; CSV generado por el medidor |
| *Pendiente* | Laboratorio con dos HackRF One por cable y atenuadores | Condición limpia en hardware, offset de la FLL, `curva_BER.csv` experimental y penalización a BER = 10⁻³ |

*Herramientas de IA:* ver la declaración de uso en la [página de inicio](index.md#uso-de-herramientas-de-inteligencia-artificial).
