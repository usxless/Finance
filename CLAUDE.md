# Hinweise für Claude

- Sprache mit dem Nutzer: Deutsch. Code-Bezeichner dürfen deutsch oder englisch sein, Ausgaben/Berichte deutsch.
- Datenquelle ist **FMP**. Für interaktive Fragen die FMP-Connector-Tools (`mcp__FMP__*`) nutzen;
  für reproduzierbare Berichte `PYTHONPATH=src FMP_API_KEY=proxy-injected python3 -m aktien analyse <TICKER>`
  (in Cloud-Sessions setzt der Proxy den echten Key ein).
- Nie Zahlen erfinden: fehlt ein Wert (null / HTTP 402), so kennzeichnen statt schätzen.
- DCF-Ergebnisse immer mit Annahmen, Sensitivität und Reverse-DCF einordnen; keine Kauf-/Verkaufsempfehlungen.
- Tests: `python3 -m pytest -q`.
