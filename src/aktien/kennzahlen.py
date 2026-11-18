"""Kennzahlen aus Jahresabschlüssen (FMP-Format, neuestes Jahr zuerst)."""

from __future__ import annotations

from dataclasses import dataclass


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b


def cagr(start: float | None, end: float | None, years: int) -> float | None:
    if not start or end is None or years <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


@dataclass
class Jahr:
    jahr: str
    umsatz: float
    umsatzwachstum: float | None
    bruttomarge: float | None
    operative_marge: float | None
    nettomarge: float | None
    fcf: float
    fcf_marge: float | None
    sbc: float
    roic: float | None
    nettoverschuldung: float
    eps_verwaessert: float | None
    aktien_verwaessert: float | None


def free_cash_flow(cf: dict) -> float:
    if cf.get("freeCashFlow") is not None:
        return cf["freeCashFlow"]
    return (cf.get("operatingCashFlow") or 0) + (cf.get("capitalExpenditure") or 0)


def nettoverschuldung(bs: dict) -> float:
    debt = bs.get("totalDebt") or 0
    cash = bs.get("cashAndShortTermInvestments")
    if cash is None:
        cash = bs.get("cashAndCashEquivalents") or 0
    return debt - cash


def roic(inc: dict, bs: dict) -> float | None:
    """NOPAT / (Eigenkapital + Schulden - Cash)."""
    ebit = inc.get("operatingIncome")
    tax_rate = safe_div(inc.get("incomeTaxExpense"), inc.get("incomeBeforeTax"))
    if ebit is None or tax_rate is None:
        return None
    tax_rate = min(max(tax_rate, 0.0), 0.5)
    invested = (bs.get("totalStockholdersEquity") or 0) + nettoverschuldung(bs)
    return safe_div(ebit * (1 - tax_rate), invested) if invested > 0 else None


def historie(income: list[dict], balance: list[dict], cash: list[dict]) -> list[Jahr]:
    """Ein Eintrag pro Geschäftsjahr, ältestes Jahr zuerst."""
    bs_by_date = {b["date"]: b for b in balance}
    cf_by_date = {c["date"]: c for c in cash}
    rows: list[Jahr] = []
    prev_rev = None
    for inc in sorted(income, key=lambda r: r["date"]):
        bs = bs_by_date.get(inc["date"], {})
        cf = cf_by_date.get(inc["date"], {})
        rev = inc.get("revenue") or 0
        fcf = free_cash_flow(cf) if cf else 0
        rows.append(
            Jahr(
                jahr=str(inc.get("fiscalYear") or inc["date"][:4]),
                umsatz=rev,
                umsatzwachstum=safe_div(rev - prev_rev, prev_rev) if prev_rev else None,
                bruttomarge=safe_div(inc.get("grossProfit"), rev),
                operative_marge=safe_div(inc.get("operatingIncome"), rev),
                nettomarge=safe_div(inc.get("netIncome"), rev),
                fcf=fcf,
                fcf_marge=safe_div(fcf, rev),
                sbc=cf.get("stockBasedCompensation") or 0,
                roic=roic(inc, bs) if bs else None,
                nettoverschuldung=nettoverschuldung(bs) if bs else 0,
                eps_verwaessert=inc.get("epsDiluted"),
                aktien_verwaessert=inc.get("weightedAverageShsOutDil"),
            )
        )
        prev_rev = rev
    return rows


def zusammenfassung(rows: list[Jahr]) -> dict[str, float | None]:
    if not rows:
        return {}
    n = len(rows) - 1
    first, last = rows[0], rows[-1]
    fcf_margins = [r.fcf_marge for r in rows if r.fcf_marge is not None]
    roics = [r.roic for r in rows if r.roic is not None]
    return {
        "umsatz_cagr": cagr(first.umsatz, last.umsatz, n),
        "eps_cagr": cagr(first.eps_verwaessert, last.eps_verwaessert, n),
        "fcf_cagr": cagr(first.fcf, last.fcf, n),
        "fcf_marge_schnitt": sum(fcf_margins) / len(fcf_margins) if fcf_margins else None,
        "roic_schnitt": sum(roics) / len(roics) if roics else None,
        "aktienanzahl_cagr": cagr(first.aktien_verwaessert, last.aktien_verwaessert, n),
        "sbc_anteil_fcf": safe_div(last.sbc, last.fcf) if last.fcf > 0 else None,
    }
