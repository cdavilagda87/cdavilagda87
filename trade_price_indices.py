"""
Índices de Precios de Comercio Exterior
=======================================
Módulo para calcular índices de precios de exportaciones e importaciones,
relación de intercambio (términos de intercambio) y variaciones de valor unitario.

Índices implementados:
  - Laspeyres (base fija, ponderación período base)
  - Paasche   (base fija, ponderación período corriente)
  - Fisher    (media geométrica de Laspeyres y Paasche)
  - Variación de Valor Unitario (VVU)
  - Términos de Intercambio (ToT)
  - Efecto Términos de Intercambio
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class Producto:
    """Representa un bien/producto en la canasta de comercio."""
    codigo: str
    descripcion: str
    # precio en el período base (p0)
    precio_base: float
    # cantidad exportada/importada en el período base (q0)
    cantidad_base: float
    # precio en el período corriente (pt)
    precio_corriente: Optional[float] = None
    # cantidad exportada/importada en el período corriente (qt)
    cantidad_corriente: Optional[float] = None

    @property
    def valor_base(self) -> float:
        """Valor total en el período base: p0 * q0"""
        return self.precio_base * self.cantidad_base

    @property
    def valor_corriente(self) -> Optional[float]:
        """Valor total en el período corriente: pt * qt"""
        if self.precio_corriente is None or self.cantidad_corriente is None:
            return None
        return self.precio_corriente * self.cantidad_corriente


@dataclass
class Canasta:
    """Canasta de productos para una corriente comercial (X o M)."""
    nombre: str                        # p.ej. 'Exportaciones' / 'Importaciones'
    productos: List[Producto] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Agregar / actualizar productos
    # ------------------------------------------------------------------
    def agregar(self, producto: Producto) -> None:
        self.productos.append(producto)

    def actualizar_corriente(self, codigo: str, precio: float, cantidad: float) -> None:
        for p in self.productos:
            if p.codigo == codigo:
                p.precio_corriente = precio
                p.cantidad_corriente = cantidad
                return
        raise KeyError(f"Producto '{codigo}' no encontrado en la canasta.")

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    def _verificar_datos_corrientes(self) -> None:
        faltantes = [p.codigo for p in self.productos
                     if p.precio_corriente is None or p.cantidad_corriente is None]
        if faltantes:
            raise ValueError(
                f"Faltan precios/cantidades corrientes para: {faltantes}"
            )

    # ------------------------------------------------------------------
    # Índice de Laspeyres de Precios
    # IPL = Σ(pt * q0) / Σ(p0 * q0)
    # ------------------------------------------------------------------
    def laspeyres(self) -> float:
        """
        Índice de Laspeyres de precios.
        Usa las cantidades del período base como ponderadores.
        """
        self._verificar_datos_corrientes()
        numerador = sum(p.precio_corriente * p.cantidad_base for p in self.productos)
        denominador = sum(p.precio_base * p.cantidad_base for p in self.productos)
        if denominador == 0:
            raise ZeroDivisionError("Valor base total es cero.")
        return numerador / denominador

    # ------------------------------------------------------------------
    # Índice de Paasche de Precios
    # IPP = Σ(pt * qt) / Σ(p0 * qt)
    # ------------------------------------------------------------------
    def paasche(self) -> float:
        """
        Índice de Paasche de precios.
        Usa las cantidades del período corriente como ponderadores.
        """
        self._verificar_datos_corrientes()
        numerador = sum(p.precio_corriente * p.cantidad_corriente for p in self.productos)
        denominador = sum(p.precio_base * p.cantidad_corriente for p in self.productos)
        if denominador == 0:
            raise ZeroDivisionError("Denominador Paasche es cero.")
        return numerador / denominador

    # ------------------------------------------------------------------
    # Índice de Fisher (media geométrica Laspeyres × Paasche)
    # ------------------------------------------------------------------
    def fisher(self) -> float:
        """Índice de Fisher: raíz cuadrada del producto Laspeyres × Paasche."""
        return math.sqrt(self.laspeyres() * self.paasche())

    # ------------------------------------------------------------------
    # Índice de Cantidad de Laspeyres
    # IQL = Σ(p0 * qt) / Σ(p0 * q0)
    # ------------------------------------------------------------------
    def laspeyres_cantidad(self) -> float:
        """Índice de Laspeyres de cantidades (volumen)."""
        self._verificar_datos_corrientes()
        numerador = sum(p.precio_base * p.cantidad_corriente for p in self.productos)
        denominador = sum(p.precio_base * p.cantidad_base for p in self.productos)
        if denominador == 0:
            raise ZeroDivisionError("Valor base total es cero.")
        return numerador / denominador

    # ------------------------------------------------------------------
    # Índice de Cantidad de Paasche
    # IQP = Σ(pt * qt) / Σ(pt * q0)
    # ------------------------------------------------------------------
    def paasche_cantidad(self) -> float:
        """Índice de Paasche de cantidades (volumen)."""
        self._verificar_datos_corrientes()
        numerador = sum(p.precio_corriente * p.cantidad_corriente for p in self.productos)
        denominador = sum(p.precio_corriente * p.cantidad_base for p in self.productos)
        if denominador == 0:
            raise ZeroDivisionError("Denominador Paasche cantidad es cero.")
        return numerador / denominador

    # ------------------------------------------------------------------
    # Variación de Valor (índice de valor corriente)
    # IV = Σ(pt * qt) / Σ(p0 * q0)
    # ------------------------------------------------------------------
    def indice_valor(self) -> float:
        """Índice de valor corriente (precio × cantidad)."""
        self._verificar_datos_corrientes()
        numerador = sum(p.precio_corriente * p.cantidad_corriente for p in self.productos)
        denominador = sum(p.precio_base * p.cantidad_base for p in self.productos)
        if denominador == 0:
            raise ZeroDivisionError("Valor base total es cero.")
        return numerador / denominador

    # ------------------------------------------------------------------
    # Variación del Valor Unitario (VVU)
    # Relación entre el valor total y la cantidad total (unidades homogéneas)
    # Solo aplicable cuando existe una unidad de medida común.
    # ------------------------------------------------------------------
    def valor_unitario_base(self) -> float:
        total_valor = sum(p.valor_base for p in self.productos)
        total_cantidad = sum(p.cantidad_base for p in self.productos)
        if total_cantidad == 0:
            raise ZeroDivisionError("Cantidad base total es cero.")
        return total_valor / total_cantidad

    def valor_unitario_corriente(self) -> float:
        self._verificar_datos_corrientes()
        total_valor = sum(p.valor_corriente for p in self.productos)
        total_cantidad = sum(p.cantidad_corriente for p in self.productos)
        if total_cantidad == 0:
            raise ZeroDivisionError("Cantidad corriente total es cero.")
        return total_valor / total_cantidad

    def indice_valor_unitario(self) -> float:
        """Índice de Variación del Valor Unitario (VVU)."""
        return self.valor_unitario_corriente() / self.valor_unitario_base()

    # ------------------------------------------------------------------
    # Ponderaciones implícitas (participación en el valor base)
    # ------------------------------------------------------------------
    def ponderaciones(self) -> Dict[str, float]:
        total = sum(p.valor_base for p in self.productos)
        if total == 0:
            raise ZeroDivisionError("Valor base total es cero.")
        return {p.codigo: p.valor_base / total for p in self.productos}

    # ------------------------------------------------------------------
    # Resumen completo de la canasta
    # ------------------------------------------------------------------
    def resumen(self) -> Dict:
        self._verificar_datos_corrientes()
        ponderaciones = self.ponderaciones()
        filas = []
        for p in self.productos:
            variacion_precio = (p.precio_corriente / p.precio_base - 1) * 100
            variacion_cantidad = (p.cantidad_corriente / p.cantidad_base - 1) * 100
            filas.append({
                "codigo": p.codigo,
                "descripcion": p.descripcion,
                "precio_base": p.precio_base,
                "precio_corriente": p.precio_corriente,
                "var_precio_%": round(variacion_precio, 2),
                "cantidad_base": p.cantidad_base,
                "cantidad_corriente": p.cantidad_corriente,
                "var_cantidad_%": round(variacion_cantidad, 2),
                "valor_base": round(p.valor_base, 4),
                "valor_corriente": round(p.valor_corriente, 4),
                "ponderacion_%": round(ponderaciones[p.codigo] * 100, 2),
            })
        return {
            "canasta": self.nombre,
            "productos": filas,
            "indices": {
                "laspeyres": round(self.laspeyres(), 6),
                "paasche": round(self.paasche(), 6),
                "fisher": round(self.fisher(), 6),
                "laspeyres_cantidad": round(self.laspeyres_cantidad(), 6),
                "paasche_cantidad": round(self.paasche_cantidad(), 6),
                "indice_valor": round(self.indice_valor(), 6),
                "indice_valor_unitario": round(self.indice_valor_unitario(), 6),
            },
        }


# ---------------------------------------------------------------------------
# Términos de Intercambio (Terms of Trade — ToT)
# ---------------------------------------------------------------------------

class TerminosDeIntercambio:
    """
    Calcula los términos de intercambio y efectos derivados.

    ToT = IPX / IPM
    donde IPX = índice de precios de exportaciones
          IPM = índice de precios de importaciones

    Un ToT > 1 indica mejora respecto al período base (los precios
    de exportación subieron más que los de importación).
    """

    def __init__(self, exportaciones: Canasta, importaciones: Canasta,
                 metodo: str = "laspeyres") -> None:
        """
        Parameters
        ----------
        exportaciones : Canasta de exportaciones
        importaciones : Canasta de importaciones
        metodo        : 'laspeyres', 'paasche' o 'fisher'
        """
        metodos_validos = {"laspeyres", "paasche", "fisher"}
        if metodo not in metodos_validos:
            raise ValueError(f"Método debe ser uno de {metodos_validos}")
        self.exportaciones = exportaciones
        self.importaciones = importaciones
        self.metodo = metodo

    def _indice(self, canasta: Canasta) -> float:
        return getattr(canasta, self.metodo)()

    def ipx(self) -> float:
        """Índice de Precios de Exportaciones."""
        return self._indice(self.exportaciones)

    def ipm(self) -> float:
        """Índice de Precios de Importaciones."""
        return self._indice(self.importaciones)

    def tot(self) -> float:
        """Relación de Intercambio: IPX / IPM."""
        ipm = self.ipm()
        if ipm == 0:
            raise ZeroDivisionError("IPM es cero.")
        return self.ipx() / ipm

    def poder_compra_exportaciones(self) -> float:
        """
        Poder de compra de las exportaciones:
        PCX = IQX × ToT
        donde IQX es el índice de cantidad de exportaciones (Laspeyres).
        """
        return self.exportaciones.laspeyres_cantidad() * self.tot()

    def efecto_terminos_intercambio(self) -> float:
        """
        Efecto Términos de Intercambio (ganancia/pérdida real):
        ETI = IQX × (ToT - 1)
        Expresado en unidades del valor base de exportaciones.
        """
        valor_base_x = sum(p.valor_base for p in self.exportaciones.productos)
        return self.exportaciones.laspeyres_cantidad() * (self.tot() - 1) * valor_base_x

    def resumen(self) -> Dict:
        return {
            "metodo": self.metodo.capitalize(),
            "IPX (Índice Precios Exportaciones)": round(self.ipx(), 6),
            "IPM (Índice Precios Importaciones)": round(self.ipm(), 6),
            "ToT (Términos de Intercambio)":      round(self.tot(), 6),
            "ToT variación %":                    round((self.tot() - 1) * 100, 2),
            "Poder Compra Exportaciones":          round(self.poder_compra_exportaciones(), 6),
            "Efecto Términos de Intercambio ($)":  round(self.efecto_terminos_intercambio(), 2),
        }


# ---------------------------------------------------------------------------
# Cálculo en serie de tiempo
# ---------------------------------------------------------------------------

@dataclass
class ObservacionTemporal:
    periodo: str                    # e.g. '2024-Q1'
    precios: Dict[str, float]       # {codigo: precio}
    cantidades: Dict[str, float]    # {codigo: cantidad}


def calcular_serie(
    canasta_base: Canasta,
    observaciones: List[ObservacionTemporal],
    metodo: str = "laspeyres",
) -> List[Dict]:
    """
    Calcula índices para una serie de períodos respecto a una canasta base.

    Returns una lista de diccionarios con el período y los índices calculados.
    """
    resultados = []
    for obs in observaciones:
        # Actualizar precios y cantidades corrientes en la canasta base
        for prod in canasta_base.productos:
            if prod.codigo in obs.precios:
                prod.precio_corriente = obs.precios[prod.codigo]
            if prod.codigo in obs.cantidades:
                prod.cantidad_corriente = obs.cantidades[prod.codigo]

        idx = getattr(canasta_base, metodo)()
        idx_vol = canasta_base.laspeyres_cantidad()
        idx_val = canasta_base.indice_valor()

        resultados.append({
            "periodo": obs.periodo,
            f"IPP_{metodo}": round(idx, 6),
            "IQ_laspeyres": round(idx_vol, 6),
            "IV": round(idx_val, 6),
            f"IPP_{metodo}_var%": round((idx - 1) * 100, 2),
        })
    return resultados


# ---------------------------------------------------------------------------
# Utilidades de presentación
# ---------------------------------------------------------------------------

def imprimir_tabla(datos: List[Dict], titulo: str = "") -> None:
    """Imprime un listado de diccionarios como tabla en consola."""
    if not datos:
        print("(sin datos)")
        return
    if titulo:
        print(f"\n{'=' * 70}")
        print(f"  {titulo}")
        print(f"{'=' * 70}")
    encabezados = list(datos[0].keys())
    anchos = {k: max(len(str(k)), max(len(str(r[k])) for r in datos))
              for k in encabezados}
    sep = "  ".join(f"{k:<{anchos[k]}}" for k in encabezados)
    print(sep)
    print("-" * len(sep))
    for fila in datos:
        print("  ".join(f"{str(fila[k]):<{anchos[k]}}" for k in encabezados))


def imprimir_resumen_dict(d: Dict, titulo: str = "") -> None:
    """Imprime un diccionario plano como tabla clave-valor."""
    if titulo:
        print(f"\n{'=' * 60}")
        print(f"  {titulo}")
        print(f"{'=' * 60}")
    ancho_k = max(len(str(k)) for k in d)
    for k, v in d.items():
        print(f"  {str(k):<{ancho_k}}  :  {v}")
