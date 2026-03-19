"""
Portfolio Rebalancer — P7

Enforces sector and single-stock concentration limits across a set of open
signals by scaling down allocations that breach configured caps.

Usage:
    from engines.portfolio_rebalancer import PortfolioRebalancer
    rebalancer = PortfolioRebalancer()
    signals = rebalancer.rebalance(signals)   # modifies 'position_size_pct' in-place

Design:
  - Groups signals by sector (from config.SECTOR_MAP or egx30_stocks table)
  - If a sector's combined pct exceeds the sector limit, all signals in that
    sector are scaled down proportionally
  - Individual signals are then capped at MAX_POSITION_PCT
  - Logs warnings whenever a cap is applied

Sector limits default to MAX_SECTOR_PCT (35%) from execution_config but can
be overridden per-sector in the constructor.
"""

import logging
from collections import defaultdict
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from config.execution_config import MAX_POSITION_PCT, MAX_SECTOR_PCT
except ImportError:
    MAX_POSITION_PCT = 0.10
    MAX_SECTOR_PCT   = 0.35

try:
    import config as _cfg
    _SECTOR_MAP: Dict[str, str] = getattr(_cfg, "SECTOR_MAP", {})
except ImportError:
    _SECTOR_MAP: Dict[str, str] = {}


def _get_sector(symbol: str, sector_override: Dict[str, str] = None) -> str:
    """Resolve sector for a symbol. Falls back to 'other'."""
    if sector_override and symbol in sector_override:
        return sector_override[symbol]
    if symbol in _SECTOR_MAP:
        return _SECTOR_MAP[symbol]
    # Strip .CA suffix and try again
    base = symbol.replace(".CA", "").replace(".EG", "")
    if base in _SECTOR_MAP:
        return _SECTOR_MAP[base]
    return "other"


def _get_position_pct(sig: Dict) -> float:
    """Extract position size from signal dict (tries multiple key names)."""
    for key in ("kelly_position_pct", "position_size_pct", "position_pct"):
        if key in sig and sig[key] is not None:
            return float(sig[key])
    return 0.08  # default 8%


def _set_position_pct(sig: Dict, value: float) -> None:
    """Write back the position size to the signal dict under all known keys."""
    for key in ("kelly_position_pct", "position_size_pct", "position_pct"):
        if key in sig:
            sig[key] = round(value, 4)
    sig["kelly_position_pct"] = round(value, 4)  # ensure at least one key is set


class PortfolioRebalancer:
    """
    Caps sector and single-stock concentrations in a list of signals,
    scaling down positions proportionally when limits are breached.
    """

    def __init__(self,
                 sector_limits: Optional[Dict[str, float]] = None,
                 stock_cap: float = MAX_POSITION_PCT,
                 default_sector_limit: float = MAX_SECTOR_PCT):
        """
        Args:
            sector_limits: Optional per-sector cap overrides, e.g.
                           {"banking": 0.30, "realestate": 0.25}.
                           Sectors not listed use default_sector_limit.
            stock_cap: Hard cap per single stock.
            default_sector_limit: Cap for sectors not in sector_limits.
        """
        self.sector_limits        = sector_limits or {}
        self.stock_cap            = stock_cap
        self.default_sector_limit = default_sector_limit

    def _sector_limit(self, sector: str) -> float:
        return self.sector_limits.get(sector.lower(), self.default_sector_limit)

    def rebalance(self, signals: List[Dict]) -> List[Dict]:
        """
        Enforce concentration limits on a list of signal dicts.

        Modifies position size in-place. Returns the same list.
        """
        if not signals:
            return signals

        # 1. Apply per-stock hard cap first
        for sig in signals:
            pct = _get_position_pct(sig)
            if pct > self.stock_cap:
                logger.warning(
                    "PortfolioRebalancer: %s position %.1f%% capped at %.1f%%",
                    sig.get("symbol", sig.get("ticker", "?")), pct * 100,
                    self.stock_cap * 100,
                )
                _set_position_pct(sig, self.stock_cap)

        # 2. Group by sector and apply sector caps
        by_sector: Dict[str, List[Dict]] = defaultdict(list)
        for sig in signals:
            sector = _get_sector(sig.get("symbol", sig.get("ticker", "")))
            by_sector[sector].append(sig)

        for sector, sigs in by_sector.items():
            limit = self._sector_limit(sector)
            total = sum(_get_position_pct(s) for s in sigs)
            if total > limit:
                scale = limit / total
                logger.warning(
                    "PortfolioRebalancer: sector '%s' combined %.1f%% > limit %.1f%% "
                    "— scaling by %.3f",
                    sector, total * 100, limit * 100, scale,
                )
                for s in sigs:
                    _set_position_pct(s, max(_get_position_pct(s) * scale, 0.01))

        return signals

    def get_sector_summary(self, signals: List[Dict]) -> Dict[str, Dict]:
        """
        Return concentration summary per sector for dashboard display.

        Returns:
            {sector: {"signals": int, "combined_pct": float, "limit_pct": float,
                       "status": "OK"|"WARNING"|"OVER_LIMIT"}}
        """
        by_sector: Dict[str, List[float]] = defaultdict(list)
        for sig in signals:
            sector = _get_sector(sig.get("symbol", sig.get("ticker", "")))
            by_sector[sector].append(_get_position_pct(sig))

        summary = {}
        for sector, pcts in sorted(by_sector.items()):
            limit   = self._sector_limit(sector)
            total   = sum(pcts)
            if total > limit:
                status = "OVER_LIMIT"
            elif total > limit * 0.85:
                status = "WARNING"
            else:
                status = "OK"
            summary[sector] = {
                "signals":       len(pcts),
                "combined_pct":  round(total * 100, 1),
                "limit_pct":     round(limit * 100, 1),
                "status":        status,
            }
        return summary
