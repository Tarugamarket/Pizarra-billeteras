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
    retorno_diario = ultimo["retornoDiario"]  # ya viene expresado en % (ej 0.0515 = 0.0515%)
    tna = retorno_diario * 365
    return round(tna, 2), ultimo["fecha"]


_COMPARATASAS_HTML = None


def _get_comparatasas_html():
    """Descarga la página una sola vez y la reutiliza para las 3 búsquedas."""
    global _COMPARATASAS_HTML
    if _COMPARATASAS_HTML is None:
        resp = requests.get(COMPARATASAS_URL, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        })
        if resp.status_code != 200:
            raise ValueError(f"comparatasas.ar respondió con status {resp.status_code}")
        if len(resp.text) < 2000:
            raise ValueError(f"comparatasas.ar devolvió una página sospechosamente corta "
                              f"({len(resp.text)} caracteres) — puede ser un bloqueo anti-bot")
        _COMPARATASAS_HTML = resp.text
    return _COMPARATASAS_HTML


def tna_desde_comparatasas(nombre_billetera, etiqueta_busqueda):
    """Busca la TNA de una billetera dentro del HTML de comparatasas.ar."""
    html = _get_comparatasas_html()

    # Patrón: "<Billetera>...NN.NN% TNA"
    patron = re.escape(etiqueta_busqueda) + r".{0,400}?(\d{1,2}[.,]\d{1,2})\s*%\s*TNA"
    match = re.search(patron, html, re.DOTALL)
    if not match:
        raise ValueError(
            f"No encontré la tasa de {nombre_billetera} en comparatasas.ar "
            f"(la página cargó bien, {len(html)} caracteres, pero el patrón de texto no coincidió — "
            f"puede que el sitio haya cambiado de formato)"
        )

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

    
