"""Einfache FCFF-DCF-Bewertung mit linear auslaufendem Wachstum.

Annahmen (alle überschreibbar):
- Basis-FCF = Free Cash Flow des letzten Geschäftsjahres, optional abzüglich
  aktienbasierter Vergütung (SBC), weil diese echte Verwässerung ist.
- Wachstum startet bei ``wachstum_start`` und fällt linear bis zum Jahr
  ``jahre`` auf ``wachstum_ewig``.
- WACC über CAPM: EK-Kosten = risikofrei + Beta * Marktrisikoprämie;
  FK-Kosten nach Steuern; Gewichte nach Marktwert EK und Buchwert FK.
- Terminal Value nach Gordon-Growth.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DCFAnnahmen:
    basis_fcf: float
    wachstum_start: float
    wachstum_ewig: float = 0.025
    jahre: int = 10
    risikofrei: float = 0.0425
    marktrisikopraemie: float = 0.05
    beta: float = 1.0
    fk_kosten_vor_steuern: float | None = None
    steuersatz: float = 0.21
    marktkapitalisierung: float = 0.0
    gesamtschulden: float = 0.0
    nettoverschuldung: float = 0.0
    aktienanzahl: float = 1.0
    wacc_override: float | None = None


@dataclass
class DCFErgebnis:
    wacc: float
    ek_kosten: float
    cashflows: list[float]
    barwert_cashflows: float
    terminal_value: float
    barwert_terminal: float
    unternehmenswert: float
    eigenkapitalwert: float
    wert_je_aktie: float
    anteil_terminal: float
    annahmen: DCFAnnahmen = field(repr=False)


def wacc(a: DCFAnnahmen) -> tuple[float, float]:
    ek_kosten = a.risikofrei + a.beta * a.marktrisikopraemie
    if a.wacc_override is not None:
        return a.wacc_override, ek_kosten
    fk = a.fk_kosten_vor_steuern if a.fk_kosten_vor_steuern is not None else a.risikofrei + 0.015
    ek, schulden = max(a.marktkapitalisierung, 0), max(a.gesamtschulden, 0)
    gesamt = ek + schulden
    if gesamt == 0:
        return ek_kosten, ek_kosten
    return ek / gesamt * ek_kosten + schulden / gesamt * fk * (1 - a.steuersatz), ek_kosten


def wachstumspfad(start: float, ewig: float, jahre: int) -> list[float]:
    if jahre == 1:
        return [start]
    return [start + (ewig - start) * i / (jahre - 1) for i in range(jahre)]


def bewerten(a: DCFAnnahmen) -> DCFErgebnis:
    r, ek_kosten = wacc(a)
    if r <= a.wachstum_ewig:
        raise ValueError(f"WACC ({r:.2%}) muss größer sein als das ewige Wachstum ({a.wachstum_ewig:.2%})")

    cashflows, fcf = [], a.basis_fcf
    for g in wachstumspfad(a.wachstum_start, a.wachstum_ewig, a.jahre):
        fcf *= 1 + g
        cashflows.append(fcf)

    pv_cf = sum(cf / (1 + r) ** (t + 1) for t, cf in enumerate(cashflows))
    tv = cashflows[-1] * (1 + a.wachstum_ewig) / (r - a.wachstum_ewig)
    pv_tv = tv / (1 + r) ** a.jahre
    ev = pv_cf + pv_tv
    equity = ev - a.nettoverschuldung
    return DCFErgebnis(
        wacc=r,
        ek_kosten=ek_kosten,
        cashflows=cashflows,
        barwert_cashflows=pv_cf,
        terminal_value=tv,
        barwert_terminal=pv_tv,
        unternehmenswert=ev,
        eigenkapitalwert=equity,
        wert_je_aktie=equity / a.aktienanzahl,
        anteil_terminal=pv_tv / ev if ev else 0.0,
        annahmen=a,
    )


def sensitivitaet(
    a: DCFAnnahmen,
    wacc_schritte: tuple[float, ...] = (-0.01, -0.005, 0.0, 0.005, 0.01),
    g_werte: tuple[float, ...] = (0.015, 0.02, 0.025, 0.03, 0.035),
) -> tuple[list[float], list[float], list[list[float | None]]]:
    """Wert je Aktie für ein Raster aus WACC (Zeilen) x ewigem Wachstum (Spalten)."""
    basis_wacc, _ = wacc(a)
    waccs = [basis_wacc + s for s in wacc_schritte]
    tabelle: list[list[float | None]] = []
    for w in waccs:
        zeile: list[float | None] = []
        for g in g_werte:
            if w <= g:
                zeile.append(None)
                continue
            var = DCFAnnahmen(**{**a.__dict__, "wacc_override": w, "wachstum_ewig": g})
            zeile.append(bewerten(var).wert_je_aktie)
        tabelle.append(zeile)
    return waccs, list(g_werte), tabelle
