            """
Actualiza tasas_fci.json con las billeteras cuyo money market es un FCI
público (Mercado Pago, Ualá, Prex, Lemon), usando la API oficial de
ArgentinaDatos.com (basada en datos de la CNV). No requiere scraping.

Las billeteras que pagan una tasa propia de cuenta remunerada (Carrefour
Banco, Naranja X, Brubank) NO están acá: esas viven en tasas_manual.json,
que se edita a mano cuando cambian (no tienen una fuente pública estable
para automatizar sin bloqueos anti-bot).

Pensado para correr 1 vez por día vía GitHub Actions.
"""

import json
import sys
import requests

API_BASE = "https://api.argentinadatos.com/v1/finanzas/fci/fondos"

FONDOS_POR_BILLETERA = {
    "Mercado Pago": "mercado-fondo-clase-a",
    "Ualá": "ualintec-ahorro-pesos-clase-a",
    "Prex": "allaria-ahorro-clase-e",
    "Lemon": "vinci-compass-liquidez-clase-f",
}


def tna_desde_fci(nombr
