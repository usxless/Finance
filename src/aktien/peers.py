"""Peer-Vergleich über TTM-Multiples und -Margen.

Es werden nur Verhältniszahlen verglichen, keine absoluten Beträge – FMP-Peers
können in anderen Währungen berichten (z. B. Samsung in KRW).
"""

from __future__ import annotations

from statistics import median
from typing import Callable

from .fmp import FMPAboError, FMPClient, FMPError

# (Spaltenname, Quelle, Feld, Formattyp)
SPALTEN: list[tuple[str, str, str, str]] = [
    ("KGV", "ratios", "priceToEarningsRatioTTM", "x"),
    ("EV/EBITDA", "metrics", "evToEBITDATTM", "x"),
    ("EV/Umsatz", "metrics", "evToSalesTTM", "x"),
    ("KUV", "ratios", "priceToSalesRatioTTM", "x"),
    ("P/FCF", "ratios", "priceToFreeCashFlowRatioTTM", "x"),
    ("FCF-Rendite", "metrics", "freeCashFlowYieldTTM", "%"),
    ("Bruttomarge", "ratios", "grossProfitMarginTTM", "%"),
    ("Op. Marge", "ratios", "operatingProfitMarginTTM", "%"),
    ("ROIC", "metrics", "returnOnInvestedCapitalTTM", "%"),
    ("Nettoversch./EBITDA", "metrics", "netDebtToEBITDATTM", "x"),
]


def peer_daten(
    client: FMPClient,
    symbol: str,
    max_peers: int = 6,
    peers: list[str] | None = None,
    warn: Callable[[str], None] = lambda _m: None,
) -> list[dict]:
    if peers is None:
        try:
            raw = client.peers(symbol)
        except FMPError as e:
            warn(f"Peers für {symbol} nicht abrufbar: {e}")
            raw = []
        raw = sorted(raw, key=lambda p: p.get("mktCap") or 0, reverse=True)
        kandidaten = [p["symbol"] for p in raw if p.get("symbol") != symbol]
    else:
        kandidaten, max_peers = list(peers), len(peers)

    zeilen, gesperrt = [], []
    for sym in [symbol, *kandidaten]:
        if len(zeilen) > max_peers:
            break
        try:
            ratios, metrics = client.ratios_ttm(sym), client.key_metrics_ttm(sym)
        except FMPAboError:
            gesperrt.append(sym)
            continue
        except FMPError as e:
            warn(f"{sym} übersprungen: {e}")
            continue
        quellen = {"ratios": ratios, "metrics": metrics}
        zeile = {"symbol": sym}
        for name, quelle, feld, _ in SPALTEN:
            zeile[name] = quellen[quelle].get(feld)
        zeilen.append(zeile)
    if gesperrt:
        warn(f"Nicht im FMP-Abo enthalten, daher ohne Peers: {', '.join(gesperrt)}")
    return zeilen


def median_zeile(zeilen: list[dict], ohne: str) -> dict:
    out: dict = {"symbol": "Median Peers"}
    for name, *_ in SPALTEN:
        werte = [z[name] for z in zeilen if z["symbol"] != ohne and isinstance(z.get(name), (int, float))]
        # KGV/Multiples <= 0 sind nicht aussagekräftig
        if SPALTEN_TYP[name] == "x" and name != "Nettoversch./EBITDA":
            werte = [w for w in werte if w > 0]
        out[name] = median(werte) if werte else None
    return out


SPALTEN_TYP = {name: typ for name, _, _, typ in SPALTEN}
