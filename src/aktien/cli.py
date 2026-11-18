"""Kommandozeile: ``python -m aktien analyse AAPL``."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .fmp import FMPClient, FMPError
from .report import Optionen, erstelle_bericht


def _prozent(s: str) -> float:
    """Akzeptiert '8', '8%' oder '0.08'."""
    v = float(s.strip().rstrip("%").replace(",", "."))
    return v / 100 if abs(v) >= 1 or s.strip().endswith("%") else v


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aktien", description="Aktienanalyse mit FMP-Daten")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyse", help="Markdown-Bericht für eine oder mehrere Aktien erzeugen")
    a.add_argument("symbole", nargs="+", help="Ticker, z. B. AAPL MSFT SAP.DE")
    a.add_argument("--wachstum", type=_prozent, help="Startwachstum FCF p. a. (Standard: Umsatz-CAGR, begrenzt auf -5 bis 15 %%)")
    a.add_argument("--ewig", type=_prozent, default=0.025, help="Ewiges Wachstum (Standard 2,5 %%)")
    a.add_argument("--jahre", type=int, default=10, help="Prognosejahre (Standard 10)")
    a.add_argument("--risikofrei", type=_prozent, default=0.0425, help="Risikofreier Zins (Standard 4,25 %%)")
    a.add_argument("--mrp", type=_prozent, default=0.05, help="Marktrisikoprämie (Standard 5 %%)")
    a.add_argument("--wacc", type=_prozent, help="WACC fest vorgeben statt CAPM")
    a.add_argument("--mit-sbc", action="store_true", help="SBC nicht vom FCF abziehen")
    a.add_argument("--peers", help="Eigene Peer-Liste, kommagetrennt")
    a.add_argument("--max-peers", type=int, default=6)
    a.add_argument("--ausgabe", default="reports", help="Zielordner (Standard: reports/)")
    a.add_argument("--stdout", action="store_true", help="Bericht nur ausgeben, nicht speichern")
    a.add_argument("--kein-cache", action="store_true")

    args = p.parse_args(argv)
    client = FMPClient(cache_dir=None if args.kein_cache else ".cache/fmp")
    opt = Optionen(
        wachstum_start=args.wachstum,
        wachstum_ewig=args.ewig,
        dcf_jahre=args.jahre,
        risikofrei=args.risikofrei,
        marktrisikopraemie=args.mrp,
        wacc=args.wacc,
        sbc_abziehen=not args.mit_sbc,
        max_peers=args.max_peers,
        peers=[s.strip().upper() for s in args.peers.split(",")] if args.peers else None,
    )

    fehler = 0
    for sym in args.symbole:
        try:
            md = erstelle_bericht(client, sym, opt)
        except FMPError as e:
            print(f"Fehler bei {sym}: {e}", file=sys.stderr)
            fehler += 1
            continue
        if args.stdout:
            print(md)
        else:
            ziel = Path(args.ausgabe) / f"{sym.upper()}_{date.today().isoformat()}.md"
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(md)
            print(f"Bericht gespeichert: {ziel}")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
