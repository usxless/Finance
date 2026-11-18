import pytest

from aktien import dcf, kennzahlen, peers
from aktien.cli import _prozent
from aktien.report import Optionen, erstelle_bericht


def jahr(y, rev, fcf, shares=100.0):
    d = f"{y}-12-31"
    inc = {
        "date": d, "fiscalYear": str(y), "reportedCurrency": "USD", "revenue": rev,
        "grossProfit": rev * 0.5, "operatingIncome": rev * 0.2, "netIncome": rev * 0.15,
        "incomeBeforeTax": rev * 0.2, "incomeTaxExpense": rev * 0.04, "interestExpense": 5.0,
        "epsDiluted": rev * 0.15 / shares, "weightedAverageShsOutDil": shares,
    }
    bs = {"date": d, "totalDebt": 100.0, "cashAndShortTermInvestments": 40.0, "totalStockholdersEquity": 500.0}
    cf = {"date": d, "operatingCashFlow": fcf + 10, "capitalExpenditure": -10.0, "freeCashFlow": fcf,
          "stockBasedCompensation": 5.0}
    return inc, bs, cf


class FakeClient:
    def __init__(self):
        rows = [jahr(2021 + i, 1000 * 1.1**i, 150 * 1.1**i, 100 - i) for i in range(5)]
        self.inc = [r[0] for r in reversed(rows)]  # FMP: neuestes zuerst
        self.bs = [r[1] for r in reversed(rows)]
        self.cf = [r[2] for r in reversed(rows)]

    def profile(self, s):
        return {"symbol": s, "companyName": "Test AG", "price": 50.0, "marketCap": 4800.0, "beta": 1.2,
                "currency": "USD", "sector": "Tech", "industry": "Software", "country": "US", "range": "40-60"}

    def income_statement(self, s, period="annual", limit=5):
        return self.inc

    def balance_sheet(self, s, period="annual", limit=5):
        return self.bs

    def cash_flow(self, s, period="annual", limit=5):
        return self.cf

    def ratios_ttm(self, s):
        return {"priceToEarningsRatioTTM": 20.0 if s == "TST" else 15.0, "grossProfitMarginTTM": 0.5}

    def key_metrics_ttm(self, s):
        return {"evToEBITDATTM": 12.0, "freeCashFlowYieldTTM": 0.05, "netDebtToEBITDATTM": 0.3}

    def peers(self, s):
        return [{"symbol": "AAA", "mktCap": 10}, {"symbol": "BBB", "mktCap": 20}]


def test_cagr_und_historie():
    c = FakeClient()
    rows = kennzahlen.historie(c.inc, c.bs, c.cf)
    assert [r.jahr for r in rows] == ["2021", "2022", "2023", "2024", "2025"]
    assert rows[1].umsatzwachstum == pytest.approx(0.10)
    assert rows[0].fcf_marge == pytest.approx(0.15)
    # ROIC = 0.2*rev*(1-0.2) / (500 + 60)
    assert rows[0].roic == pytest.approx(160 / 560)
    zus = kennzahlen.zusammenfassung(rows)
    assert zus["umsatz_cagr"] == pytest.approx(0.10)
    assert zus["aktienanzahl_cagr"] < 0


def test_dcf_ewige_rente_ohne_wachstum():
    a = dcf.DCFAnnahmen(basis_fcf=100, wachstum_start=0, wachstum_ewig=0, jahre=5,
                        wacc_override=0.10, nettoverschuldung=0, aktienanzahl=10)
    e = dcf.bewerten(a)
    assert e.unternehmenswert == pytest.approx(1000)
    assert e.wert_je_aktie == pytest.approx(100)


def test_dcf_wacc_capm():
    a = dcf.DCFAnnahmen(basis_fcf=1, wachstum_start=0, risikofrei=0.04, marktrisikopraemie=0.05, beta=1.2,
                        fk_kosten_vor_steuern=0.05, steuersatz=0.2, marktkapitalisierung=800, gesamtschulden=200)
    w, ke = dcf.wacc(a)
    assert ke == pytest.approx(0.10)
    assert w == pytest.approx(0.8 * 0.10 + 0.2 * 0.05 * 0.8)


def test_dcf_fehler_wenn_wacc_zu_klein():
    with pytest.raises(ValueError):
        dcf.bewerten(dcf.DCFAnnahmen(basis_fcf=1, wachstum_start=0, wachstum_ewig=0.05, wacc_override=0.04))


def test_sensitivitaet_monoton():
    a = dcf.DCFAnnahmen(basis_fcf=100, wachstum_start=0.05, wacc_override=0.09, aktienanzahl=10)
    waccs, gs, tab = dcf.sensitivitaet(a)
    mitte = tab[2]
    assert all(x < y for x, y in zip(mitte, mitte[1:]))  # höheres g -> höherer Wert
    spalte = [z[2] for z in tab]
    assert all(x > y for x, y in zip(spalte, spalte[1:]))  # höherer WACC -> niedrigerer Wert


def test_peer_median_ignoriert_negative_multiples():
    zeilen = [{"symbol": "X", "KGV": 30.0}, {"symbol": "A", "KGV": -5.0}, {"symbol": "B", "KGV": 10.0},
              {"symbol": "C", "KGV": 20.0}]
    m = peers.median_zeile(zeilen, ohne="X")
    assert m["KGV"] == 15.0


def test_bericht_end_to_end():
    md = erstelle_bericht(FakeClient(), "tst", Optionen())
    assert md.startswith("# Test AG (TST)")
    for abschnitt in ("## Bewertung (TTM)", "## DCF-Bewertung", "Sensitivität", "## Peer-Vergleich", "Median Peers"):
        assert abschnitt in md
    assert "BBB" in md and "AAA" in md


@pytest.mark.parametrize("ein,aus", [("8", 0.08), ("8%", 0.08), ("0.08", 0.08), ("2,5", 0.025), ("-3", -0.03)])
def test_prozent_parser(ein, aus):
    assert _prozent(ein) == pytest.approx(aus)


def test_peers_ueberspringen_gesperrte_und_fuellen_auf():
    from aktien.fmp import FMPAboError

    class C(FakeClient):
        def peers(self, s):
            return [{"symbol": x, "mktCap": 100 - i} for i, x in enumerate(["G1", "P1", "G2", "P2", "P3"])]

        def ratios_ttm(self, s):
            if s.startswith("G"):
                raise FMPAboError("gesperrt")
            return super().ratios_ttm(s)

    warnungen = []
    zeilen = peers.peer_daten(C(), "TST", max_peers=2, warn=warnungen.append)
    assert [z["symbol"] for z in zeilen] == ["TST", "P1", "P2"]
    assert warnungen == ["Nicht im FMP-Abo enthalten, daher ohne Peers: G1, G2"]
