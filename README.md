# Finance – Aktienanalyse mit FMP

Erzeugt Analyseberichte (Markdown) für Aktien auf Basis von
[Financial Modeling Prep](https://financialmodelingprep.com):

- **Profil & Bewertung (TTM):** KGV, EV/EBITDA, EV/Umsatz, P/FCF, FCF-Rendite, Dividende, KBV
- **5-Jahres-Historie:** Umsatz, Wachstum, Margen, FCF, ROIC, EPS, CAGRs, Rückkäufe, SBC-Anteil
- **DCF-Bewertung:** FCFF-Modell (FCF nach SBC, auslaufendes Wachstum, WACC per CAPM),
  Sensitivitätstabelle WACC × ewiges Wachstum und **Reverse-DCF** (welches Wachstum preist der Kurs ein?)
- **Peer-Vergleich:** Multiples und Margen gegen FMP-Peers oder eine eigene Liste, inkl. Median

> Keine Anlageberatung. Die Modelle sind Werkzeuge zum Nachdenken, kein Kursziel.

## Einrichtung

```bash
pip install -e ".[dev]"
export FMP_API_KEY=dein_key        # aus dem FMP-Dashboard
```

In Claude-Code-Cloud-Sessions ist der Key als Netzwerk-Secret der Umgebung hinterlegt
und wird vom Proxy eingesetzt; dort genügt `export FMP_API_KEY=proxy-injected`.

## Nutzung

```bash
aktien analyse AAPL                          # -> reports/AAPL_<datum>.md
aktien analyse AAPL MSFT NVDA                # mehrere auf einmal
aktien analyse AAPL --peers MSFT,GOOGL,AMZN  # eigene Peers
aktien analyse AAPL --wachstum 8 --ewig 3 --wacc 9   # eigene DCF-Annahmen (in %)
aktien analyse AAPL --mit-sbc --stdout       # SBC nicht abziehen, nur ausgeben
```

Ohne Installation: `PYTHONPATH=src python -m aktien analyse AAPL`.

Alle Optionen: `aktien analyse --help`. Antworten werden 24 h in `.cache/fmp/` zwischengespeichert
(`--kein-cache` zum Umgehen).

## Hinweise zum FMP-Abo

Der kostenlose FMP-Plan deckt nur eine Auswahl großer US-Werte ab. Andere Symbole
(z. B. `SAP`, `SAP.DE`, `DELL`, viele ausländische Peers) liefern HTTP 402. Der Bericht überspringt solche
Peers und listet sie unter „Hinweise“. Für deutsche/europäische Börsenplätze ist ein bezahlter Plan nötig.

## Struktur

| Datei | Inhalt |
|---|---|
| `src/aktien/fmp.py` | REST-Client (Key im Header, Cache, Abo-Fehler) |
| `src/aktien/kennzahlen.py` | Historie, Margen, ROIC, CAGRs |
| `src/aktien/dcf.py` | DCF, WACC, Sensitivität |
| `src/aktien/peers.py` | Peer-Multiples und Median |
| `src/aktien/report.py` | Zusammenbau des Markdown-Berichts, Reverse-DCF |
| `src/aktien/cli.py` | Kommandozeile |
| `tests/` | Tests mit synthetischen Daten (`pytest`) |
