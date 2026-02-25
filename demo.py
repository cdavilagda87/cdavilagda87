"""
Demo — Índices de Precios de Comercio Exterior
===============================================
Ejemplo con datos ilustrativos de una economía exportadora
de materias primas e importadora de manufacturas.
"""

from trade_price_indices import (
    Producto,
    Canasta,
    TerminosDeIntercambio,
    ObservacionTemporal,
    calcular_serie,
    imprimir_tabla,
    imprimir_resumen_dict,
)

# ===========================================================================
# 1. DEFINICIÓN DE LA CANASTA BASE (período t=0)
# ===========================================================================

# --- Exportaciones ---
exportaciones = Canasta("Exportaciones")
exportaciones.agregar(Producto("SOJA",  "Soja y derivados",    precio_base=400.0, cantidad_base=1_000_000))
exportaciones.agregar(Producto("MAIZ",  "Maíz",                precio_base=180.0, cantidad_base=  800_000))
exportaciones.agregar(Producto("PETRO", "Petróleo crudo",      precio_base= 75.0, cantidad_base=  500_000))
exportaciones.agregar(Producto("COBRE", "Mineral de cobre",    precio_base=8_500.0, cantidad_base=   20_000))

# --- Importaciones ---
importaciones = Canasta("Importaciones")
importaciones.agregar(Producto("MAQUI", "Maquinaria industrial", precio_base=50_000.0, cantidad_base= 2_000))
importaciones.agregar(Producto("AUTOM", "Automóviles",           precio_base=25_000.0, cantidad_base= 5_000))
importaciones.agregar(Producto("QUIM",  "Productos químicos",    precio_base=  1_200.0, cantidad_base=80_000))
importaciones.agregar(Producto("ELEC",  "Electrónica",           precio_base=  3_500.0, cantidad_base=30_000))

# ===========================================================================
# 2. DATOS DEL PERÍODO CORRIENTE (t=1)
# ===========================================================================

# Exportaciones período corriente (precios subieron, cantidades ligeramente ajustadas)
exportaciones.actualizar_corriente("SOJA",  precio=450.0, cantidad= 980_000)
exportaciones.actualizar_corriente("MAIZ",  precio=195.0, cantidad= 820_000)
exportaciones.actualizar_corriente("PETRO", precio= 82.0, cantidad= 490_000)
exportaciones.actualizar_corriente("COBRE", precio=9_200.0, cantidad=  21_000)

# Importaciones período corriente (manufactura más cara por tipo de cambio)
importaciones.actualizar_corriente("MAQUI", precio=54_000.0, cantidad= 1_900)
importaciones.actualizar_corriente("AUTOM", precio=27_500.0, cantidad= 4_800)
importaciones.actualizar_corriente("QUIM",  precio= 1_300.0, cantidad=82_000)
importaciones.actualizar_corriente("ELEC",  precio= 3_800.0, cantidad=29_500)

# ===========================================================================
# 3. CÁLCULO DE ÍNDICES POR CANASTA
# ===========================================================================

print("\n" + "=" * 70)
print("  ÍNDICES DE PRECIOS DE COMERCIO EXTERIOR")
print("  Período base: t0  |  Período corriente: t1")
print("=" * 70)

for canasta in [exportaciones, importaciones]:
    res = canasta.resumen()
    print(f"\n{'─' * 70}")
    print(f"  CANASTA: {res['canasta'].upper()}")
    print(f"{'─' * 70}")
    imprimir_tabla(res["productos"],
                   titulo=f"Detalle por producto — {res['canasta']}")
    print(f"\n  Ponderaciones (participación en valor base):")
    pond = canasta.ponderaciones()
    for cod, w in pond.items():
        print(f"    {cod}  {w*100:6.2f} %")

    print(f"\n  Índices de precios:")
    for nombre, val in res["indices"].items():
        variacion = (val - 1) * 100
        print(f"    {nombre:<30}  {val:.6f}   ({variacion:+.2f} %)")

# ===========================================================================
# 4. TÉRMINOS DE INTERCAMBIO
# ===========================================================================

for metodo in ["laspeyres", "paasche", "fisher"]:
    tot = TerminosDeIntercambio(exportaciones, importaciones, metodo=metodo)
    imprimir_resumen_dict(
        tot.resumen(),
        titulo=f"Términos de Intercambio — Método {metodo.capitalize()}"
    )

# ===========================================================================
# 5. SERIE DE TIEMPO (ejemplo trimestral)
# ===========================================================================

print("\n" + "=" * 70)
print("  SERIE TRIMESTRAL — Índice de Precios de Exportaciones (Laspeyres)")
print("=" * 70)

# Canasta base fresca para la serie
expo_serie = Canasta("Exportaciones")
expo_serie.agregar(Producto("SOJA",  "Soja",    precio_base=400.0, cantidad_base=1_000_000))
expo_serie.agregar(Producto("MAIZ",  "Maíz",    precio_base=180.0, cantidad_base=  800_000))
expo_serie.agregar(Producto("PETRO", "Petróleo",precio_base= 75.0, cantidad_base=  500_000))
expo_serie.agregar(Producto("COBRE", "Cobre",   precio_base=8_500.0, cantidad_base=20_000))

observaciones = [
    ObservacionTemporal(
        "2024-Q1",
        precios={"SOJA": 415, "MAIZ": 183, "PETRO": 77,   "COBRE": 8_700},
        cantidades={"SOJA": 990_000, "MAIZ": 805_000, "PETRO": 498_000, "COBRE": 20_500},
    ),
    ObservacionTemporal(
        "2024-Q2",
        precios={"SOJA": 430, "MAIZ": 188, "PETRO": 79,   "COBRE": 8_900},
        cantidades={"SOJA": 985_000, "MAIZ": 810_000, "PETRO": 495_000, "COBRE": 20_800},
    ),
    ObservacionTemporal(
        "2024-Q3",
        precios={"SOJA": 445, "MAIZ": 192, "PETRO": 81,   "COBRE": 9_050},
        cantidades={"SOJA": 982_000, "MAIZ": 815_000, "PETRO": 492_000, "COBRE": 21_000},
    ),
    ObservacionTemporal(
        "2024-Q4",
        precios={"SOJA": 450, "MAIZ": 195, "PETRO": 82,   "COBRE": 9_200},
        cantidades={"SOJA": 980_000, "MAIZ": 820_000, "PETRO": 490_000, "COBRE": 21_000},
    ),
]

serie = calcular_serie(expo_serie, observaciones, metodo="laspeyres")
imprimir_tabla(serie, titulo="Serie trimestral — Exportaciones")

print("\n[Leyenda]")
print("  IPP_laspeyres  : Índice de Precios (Laspeyres), base = 1.0")
print("  IQ_laspeyres   : Índice de Cantidades (volumen físico)")
print("  IV             : Índice de Valor (precio × cantidad)")
print("  IPP_var%       : Variación porcentual del índice de precios respecto al período base")
