"""
Actualiza tasas.json combinando dos fuentes:

1) API oficial (ArgentinaDatos.com -> datos de CNV) para billeteras
   cuyo money market es un FCI público: Mercado Pago, Ualá, Prex, Lemon.
   No requiere scraping: es JSON servido por una API pública y gratuita.

2) Scraping de comparatasas.ar/cuentas-billeteras (proyecto open source
   que ya normaliza estas tasas) para las billeteras que pagan una tasa
   propia de cuenta remunerada y no están atadas a un fondo público:
   Carrefour Banco, Naranja X, Brubank.

Pensado para correr 1 vez por día vía GitHub Actions.
"""

import json
import re
import sys
import requests

API_BASE = "https://api.argentinadatos.com/v1/finanzas/fci/fondos"
COMPARATASAS_URL = "https://comparatasas.ar/cuentas-billeteras"

# billetera -> nombre normalizado del fondo en ArgentinaDatos
FONDOS_POR_BILLETERA = {
    "Mercado Pago": "mercado-fondo-clase-a",
    "Ualá": "ualintec-ahorro-pesos-clase-a",
    "Prex": "allaria-ahorro-clase-e",
    "Lemon": "vinci-compass-liquidez-clase-f",
}

# billetera -> texto exacto como aparece en comparatasas.ar
DIRECTAS_EN_COMPARATASAS = {
    "Carrefour Banco": "Carrefour Banco",
    "Naranja X": "Naranja X",
    "Brubank": "Brubank",
}


def tna_desde_fci(nombre_fondo):
    """Trae el histórico del fondo y anualiza el último retorno diario."""
    url = f"{API_BASE}/{nombre_fondo}/historico"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    historico = data.get("historico", [])
    if not historico:
        raise ValueError(f"Sin histórico para {nombre_fondo}")

    ultimo = historico[-1]
    retorno_diario = ultimo["retornoDiario"]  # verificar si viene en % o fracción
    # Si retornoDiario viene como fracción (ej 0.00075) -> TNA = retorno*365*100
    # Si ya viene en % (ej 0.075) -> TNA = retorno*365
    # Chequeá el valor real la primera vez que corras esto y ajustá el factor.
    tna = retorno_diario * 365 * 100
    return round(tna, 2), ultimo["fecha"]


def tna_desde_comparatasas(nombre_billetera, etiqueta_busqueda):
    """Busca la TNA de una billetera dentro del HTML de comparatasas.ar."""
    resp = requests.get(COMPARATASAS_URL, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (compatible; PizarraBot/1.0)"
    })
    resp.raise_for_status()
    html = resp.text

    # Patrón: "<Billetera>...NN.NN% TNA"
    patron = re.escape(etiqueta_busqueda) + r".{0,400}?(\d{1,2}[.,]\d{1,2})\s*%\s*TNA"
    match = re.search(patron, html, re.DOTALL)
    if not match:
        raise ValueError(f"No encontré la tasa de {nombre_billetera} en comparatasas.ar")

    tna = float(match.group(1).replace(",", "."))
    return tna


def main():
    resultado = []
    errores = []

    for billetera, fondo in FONDOS_POR_BILLETERA.items():
        try:
            tna, fecha = tna_desde_fci(fondo)
            resultado.append({
                "nombre": billetera,
                "nota": "fondo FCI",
                "tna": tna,
                "fuente": "ArgentinaDatos (CNV)",
                "fecha": fecha,
            })
        except Exception as e:
            errores.append(f"{billetera}: {e}")

    for billetera, etiqueta in DIRECTAS_EN_COMPARATASAS.items():
        try:
            tna = tna_desde_comparatasas(billetera, etiqueta)
            resultado.append({
                "nombre": billetera,
                "tna": tna,
                "fuente": "comparatasas.ar",
            })
        except Exception as e:
            errores.append(f"{billetera}: {e}")

    if not resultado:
        print("No se pudo obtener ninguna tasa. Abortando sin tocar tasas.json.", file=sys.stderr)
        sys.exit(1)

    with open("tasas.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"tasas.json actualizado con {len(resultado)} billeteras.")
    if errores:
        print("Avisos (no bloquean la corrida):", file=sys.stderr)
        for e in errores:
            print(f"  - {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
