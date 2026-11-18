"""Erzeugt einen Markdown-Analysebericht für eine Aktie."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import dcf, kennzahlen, peers
from .fmp import FMPClient


@dataclass
class Optionen:
    jahre_historie: int = 5
    wachstum_start: float | None = None  # None = aus Umsatz-CAGR ableiten
    wachstum_ewig: float = 0.025
    dcf_jahre: int = 10
    risikofrei: float = 0.0425
    marktrisikopraemie: float = 0.05
    wacc: float | None = None
    sbc_abziehen: bool = True
    max_peers: int = 6
    peers: list[str] | None = None


# -- Formatierung --------------------------------------------------------------
def pct(v: float | None, nachkomma: int = 1) -> str:
    return "–" if v is None else f"{v * 100:.{nachkomma}f} %"


def mult(v: float | None) -> str:
    return "–" if v is None else f"{v:.1f}x"


def geld(v: float | None, waehrung: str = "") -> str:
    if v is None:
        return "–"
    a = abs(v)
    for grenze, suffix in ((1e12, "Bio."), (1e9, "Mrd."), (1e6, "Mio.")):
        if a >= grenze:
            return f"{v / grenze:,.1f} {suffix} {waehrung}".strip()
    return f"{v:,.2f} {waehrung}".strip()


def tabelle(kopf: list[str], zeilen: list[list[str]]) -> str:
    out = ["| " + " | ".join(kopf) + " |", "|" + "|".join("---" for _ in kopf) + "|"]
    out += ["| " + " | ".join(z) + " |" for z in zeilen]
    return "\n".join(out)


# -- Bericht -----------------------------------------------------------------
def dcf_annahmen(profil: dict, inc: list[dict], bs: list[dict], cf: list[dict], opt: Optionen) -> DCFAnnahmenMitInfo:
    rows = kennzahlen.historie(inc, bs, cf)
    zus = kennzahlen.zusammenfassung(rows)
    last_inc = max(inc, key=lambda r: r["date"])
    last_bs = max(bs, key=lambda r: r["date"])
    last_cf = max(cf, key=lambda r: r["date"])

    basis = kennzahlen.free_cash_flow(last_cf)
    if opt.sbc_abziehen:
        basis -= last_cf.get("stockBasedCompensation") or 0

    g0 = opt.wachstum_start
    if g0 is None:
        g0 = min(max(zus.get("umsatz_cagr") or 0.03, -0.05), 0.15)

    steuer = kennzahlen.safe_div(last_inc.get("incomeTaxExpense"), last_inc.get("incomeBeforeTax"))
    steuer = 0.21 if steuer is None else min(max(steuer, 0.0), 0.35)
    fk = kennzahlen.safe_div(last_inc.get("interestExpense"), last_bs.get("totalDebt"))
    if fk is not None and not (0.005 < fk < 0.20):
        fk = None

    preis = profil.get("price") or 0
    mcap = profil.get("marketCap") or 0
    aktien = mcap / preis if preis else (last_inc.get("weightedAverageShsOutDil") or 1)

    a = dcf.DCFAnnahmen(
        basis_fcf=basis,
        wachstum_start=g0,
        wachstum_ewig=opt.wachstum_ewig,
        jahre=opt.dcf_jahre,
        risikofrei=opt.risikofrei,
        marktrisikopraemie=opt.marktrisikopraemie,
        beta=profil.get("beta") or 1.0,
        fk_kosten_vor_steuern=fk,
        steuersatz=steuer,
        marktkapitalisierung=mcap,
        gesamtschulden=last_bs.get("totalDebt") or 0,
        nettoverschuldung=kennzahlen.nettoverschuldung(last_bs),
        aktienanzahl=aktien,
        wacc_override=opt.wacc,
    )
    return DCFAnnahmenMitInfo(a, rows, zus)


@dataclass
class DCFAnnahmenMitInfo:
    annahmen: dcf.DCFAnnahmen
    historie: list[kennzahlen.Jahr]
    zusammenfassung: dict


def erstelle_bericht(client: FMPClient, symbol: str, opt: Optionen | None = None) -> str:
    opt = opt or Optionen()
    symbol = symbol.upper()
    warnungen: list[str] = []

    profil = client.profile(symbol)
    inc = client.income_statement(symbol, limit=opt.jahre_historie)
    bs = client.balance_sheet(symbol, limit=opt.jahre_historie)
    cf = client.cash_flow(symbol, limit=opt.jahre_historie)
    ratios = client.ratios_ttm(symbol)
    metrics = client.key_metrics_ttm(symbol)
    w = profil.get("currency", "")
    rep_w = inc[0].get("reportedCurrency", w) if inc else w
    if rep_w and w and rep_w != w:
        warnungen.append(
            f"Kurs in {w}, Abschlüsse in {rep_w}: Der DCF-Wert je Aktie ist in {rep_w} und nicht direkt mit dem Kurs vergleichbar."
        )

    info = dcf_annahmen(profil, inc, bs, cf, opt)
    a, rows, zus = info.annahmen, info.historie, info.zusammenfassung
    teile: list[str] = []

    # Kopf
    teile.append(f"# {profil.get('companyName', symbol)} ({symbol})")
    teile.append(
        f"*Stand {date.today().isoformat()} · Daten: Financial Modeling Prep · "
        "keine Anlageberatung*"
    )
    teile.append(
        tabelle(
            ["Kurs", "Marktkap.", "Beta", "Sektor / Branche", "Land", "52W-Spanne"],
            [[
                geld(profil.get("price"), w),
                geld(profil.get("marketCap"), w),
                f"{profil.get('beta') or 0:.2f}",
                f"{profil.get('sector', '–')} / {profil.get('industry', '–')}",
                profil.get("country", "–"),
                profil.get("range", "–"),
            ]],
        )
    )

    # Bewertung TTM
    teile.append("## Bewertung (TTM)")
    teile.append(
        tabelle(
            ["KGV", "EV/EBITDA", "EV/Umsatz", "P/FCF", "FCF-Rendite", "Div.-Rendite", "KBV"],
            [[
                mult(ratios.get("priceToEarningsRatioTTM")),
                mult(metrics.get("evToEBITDATTM")),
                mult(metrics.get("evToSalesTTM")),
                mult(ratios.get("priceToFreeCashFlowRatioTTM")),
                pct(metrics.get("freeCashFlowYieldTTM")),
                pct(ratios.get("dividendYieldTTM"), 2),
                mult(ratios.get("priceToBookRatioTTM")),
            ]],
        )
    )

    # Historie
    teile.append(f"## Entwicklung der letzten {len(rows)} Geschäftsjahre")
    teile.append(
        tabelle(
            ["GJ", "Umsatz", "Wachstum", "Bruttom.", "Op. Marge", "Nettom.", "FCF", "FCF-Marge", "ROIC¹", "EPS (verw.)"],
            [[
                r.jahr, geld(r.umsatz, rep_w), pct(r.umsatzwachstum), pct(r.bruttomarge),
                pct(r.operative_marge), pct(r.nettomarge), geld(r.fcf, rep_w), pct(r.fcf_marge),
                pct(r.roic), "–" if r.eps_verwaessert is None else f"{r.eps_verwaessert:.2f}",
            ] for r in rows],
        )
    )
    teile.append(
        "\n".join([
            "- ¹ ROIC eigene Berechnung: NOPAT / (Eigenkapital + Nettoverschuldung); weicht von FMPs TTM-ROIC im Peer-Vergleich ab",
            f"- Umsatz-CAGR: **{pct(zus.get('umsatz_cagr'))}**, EPS-CAGR: **{pct(zus.get('eps_cagr'))}**, FCF-CAGR: **{pct(zus.get('fcf_cagr'))}**",
            f"- Ø FCF-Marge: **{pct(zus.get('fcf_marge_schnitt'))}**, Ø ROIC: **{pct(zus.get('roic_schnitt'))}**",
            f"- Veränderung Aktienanzahl p. a.: **{pct(zus.get('aktienanzahl_cagr'))}** (negativ = Rückkäufe)",
            f"- SBC in % vom FCF (letztes GJ): **{pct(zus.get('sbc_anteil_fcf'))}**",
            f"- Nettoverschuldung: **{geld(rows[-1].nettoverschuldung if rows else None, rep_w)}**, "
            f"Nettoversch./EBITDA: **{mult(metrics.get('netDebtToEBITDATTM'))}**",
        ])
    )

    # DCF
    teile.append("## DCF-Bewertung")
    try:
        erg = dcf.bewerten(a)
        preis = profil.get("price") or 0
        potenzial = erg.wert_je_aktie / preis - 1 if preis else None
        teile.append(
            "\n".join([
                f"- Basis-FCF{' (nach SBC)' if opt.sbc_abziehen else ''}: **{geld(a.basis_fcf, rep_w)}**",
                f"- Wachstum: {pct(a.wachstum_start)} im 1. Jahr, linear fallend auf {pct(a.wachstum_ewig)} ewig ({a.jahre} Jahre)",
                f"- WACC: **{pct(erg.wacc, 2)}** (EK-Kosten {pct(erg.ek_kosten, 2)} = {pct(a.risikofrei, 2)} + {a.beta:.2f} × {pct(a.marktrisikopraemie, 1)}; Steuersatz {pct(a.steuersatz)})",
                f"- Unternehmenswert: {geld(erg.unternehmenswert, rep_w)}, davon Terminal Value {pct(erg.anteil_terminal)}",
                f"- **Fairer Wert je Aktie: {erg.wert_je_aktie:,.2f} {rep_w}** vs. Kurs {preis:,.2f} {w} → **{pct(potenzial)}**",
            ])
        )
        waccs, gs, tab = dcf.sensitivitaet(a)
        teile.append("**Sensitivität: Wert je Aktie (Zeilen WACC, Spalten ewiges Wachstum)**")
        teile.append(
            tabelle(
                ["WACC \\ g", *[pct(g) for g in gs]],
                [[pct(wc, 2), *["–" if v is None else f"{v:,.0f}" for v in zeile]] for wc, zeile in zip(waccs, tab)],
            )
        )
        # Reverse-DCF: welches Startwachstum preist der Markt ein?
        impl = implizites_wachstum(a, preis)
        if impl is not None:
            teile.append(f"*Reverse-DCF: Der aktuelle Kurs impliziert ein Startwachstum von ca. **{pct(impl)}** (bei sonst gleichen Annahmen).*")
    except ValueError as e:
        teile.append(f"DCF nicht berechenbar: {e}")
    if a.basis_fcf <= 0:
        warnungen.append("Basis-FCF ist negativ oder null, daher ist der DCF wenig aussagekräftig.")

    # Peers
    teile.append("## Peer-Vergleich (TTM)")
    zeilen = peers.peer_daten(client, symbol, opt.max_peers, opt.peers, warn=warnungen.append)
    if len(zeilen) > 1:
        zeilen.append(peers.median_zeile(zeilen, ohne=symbol))
        kopf = ["Symbol", *[s[0] for s in peers.SPALTEN]]
        fmt = lambda name, v: pct(v) if peers.SPALTEN_TYP[name] == "%" else mult(v)  # noqa: E731
        teile.append(
            tabelle(kopf, [[f"**{z['symbol']}**" if z["symbol"] == symbol else z["symbol"],
                            *[fmt(s[0], z.get(s[0])) for s in peers.SPALTEN]] for z in zeilen])
        )
        teile.append("*Peers laut FMP; können ausländische Werte enthalten. Mit `--peers` eigene Liste setzen.*")
    else:
        teile.append("Keine Peer-Daten verfügbar.")

    if warnungen:
        teile.append("## Hinweise")
        teile.append("\n".join(f"- {m}" for m in warnungen))

    return "\n\n".join(teile) + "\n"


def implizites_wachstum(a: dcf.DCFAnnahmen, preis: float) -> float | None:
    """Bisektion auf das Startwachstum, sodass Wert je Aktie == Kurs."""
    if preis <= 0 or a.basis_fcf <= 0:
        return None

    def wert(g: float) -> float:
        return dcf.bewerten(dcf.DCFAnnahmen(**{**a.__dict__, "wachstum_start": g})).wert_je_aktie

    lo, hi = -0.20, 0.60
    try:
        if not (wert(lo) <= preis <= wert(hi)):
            return None
    except ValueError:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if wert(mid) < preis:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
