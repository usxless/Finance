"""Schlanker Client für die FMP "stable" REST-API.

Der API-Key kommt aus der Umgebungsvariable ``FMP_API_KEY`` und wird im
Header ``apikey`` gesendet (nie in der URL, damit er nicht in Logs landet).
Ist keine Variable gesetzt, geht die Anfrage ohne Key raus – nützlich, wenn
ein Proxy den Key einsetzt.

Antworten werden standardmäßig einen Tag lang unter ``.cache/fmp`` gespeichert,
um das Abrufkontingent zu schonen.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://financialmodelingprep.com/stable"


class FMPError(RuntimeError):
    pass


class FMPAboError(FMPError):
    """HTTP 402: Endpunkt oder Symbol ist im aktuellen FMP-Abo nicht enthalten."""


class FMPClient:
    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | Path | None = ".cache/fmp",
        cache_ttl: int = 24 * 3600,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("FMP_API_KEY")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_ttl = cache_ttl
        self.session = session or requests.Session()

    # -- Basis ---------------------------------------------------------------
    def get(self, path: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        cache_file = self._cache_file(path, params)
        if cache_file and cache_file.exists() and time.time() - cache_file.stat().st_mtime < self.cache_ttl:
            return json.loads(cache_file.read_text())

        headers = {"apikey": self.api_key} if self.api_key else {}
        resp = self.session.get(f"{BASE_URL}/{path}", params=params, headers=headers, timeout=30)
        if resp.status_code == 402:
            raise FMPAboError(f"{path}?symbol={params.get('symbol', '')}: nicht im FMP-Abo enthalten")
        if resp.status_code != 200:
            raise FMPError(f"FMP {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if isinstance(data, dict) and ("Error Message" in data or "error" in data):
            raise FMPError(f"FMP {path}: {data}")

        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data))
        return data

    def _cache_file(self, path: str, params: dict[str, Any]) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha1(json.dumps([path, sorted(params.items())]).encode()).hexdigest()[:16]
        return self.cache_dir / f"{path.replace('/', '_')}_{key}.json"

    # -- Endpunkte -----------------------------------------------------------
    def profile(self, symbol: str) -> dict:
        return _first(self.get("profile", symbol=symbol), symbol)

    def quote(self, symbol: str) -> dict:
        return _first(self.get("quote", symbol=symbol), symbol)

    def income_statement(self, symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
        return self.get("income-statement", symbol=symbol, period=period, limit=limit)

    def balance_sheet(self, symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
        return self.get("balance-sheet-statement", symbol=symbol, period=period, limit=limit)

    def cash_flow(self, symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
        return self.get("cash-flow-statement", symbol=symbol, period=period, limit=limit)

    def key_metrics_ttm(self, symbol: str) -> dict:
        return _first(self.get("key-metrics-ttm", symbol=symbol), symbol)

    def ratios_ttm(self, symbol: str) -> dict:
        return _first(self.get("ratios-ttm", symbol=symbol), symbol)

    def peers(self, symbol: str) -> list[dict]:
        return self.get("stock-peers", symbol=symbol)


def _first(data: Any, symbol: str) -> dict:
    if not data:
        raise FMPError(f"Keine Daten für {symbol}")
    return data[0] if isinstance(data, list) else data
