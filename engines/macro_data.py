"""
MacroDataProvider — fetches and caches Egypt macro indicators.

Indicators:
  - CBE overnight rate (proxy: Egypt 91-day T-bill rate)
  - USD/EGP spot rate
  - Egypt CPI YoY %
  - Egypt GDP growth %

Caching:
  - Macro data is slow-moving; cached to `macro_indicators` table
  - Refreshed daily via GitHub Actions `daily-pipeline` job
  - Serves stale cache on fetch failure — never blocks simulation on macro fetch failure

Schema: macro_indicators table
  id SERIAL PRIMARY KEY,
  indicator TEXT NOT NULL,        -- 'cbe_rate', 'usd_egp', 'cpi_yoy', 'gdp_growth'
  value REAL NOT NULL,
  period TEXT NOT NULL,           -- 'YYYY-MM' or 'YYYY-QQ'
  source TEXT NOT NULL,           -- 'FRED', 'WorldBank', 'yfinance', 'manual'
  fetched_at TIMESTAMP DEFAULT NOW()
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

# Default values for when APIs are unavailable
_DEFAULTS = {
    'cbe_rate': {'value': 27.25, 'period': '2026-03', 'source': 'manual'},
    'usd_egp': {'value': 50.85, 'period': '2026-04', 'source': 'manual'},
    'cpi_yoy': {'value': 13.6, 'period': '2026-02', 'source': 'manual'},
    'gdp_growth': {'value': 3.5, 'period': '2025-Q4', 'source': 'manual'},
}


class MacroDataProvider:
    """
    Fetches and caches Egypt macro indicators.

    Usage:
        provider = MacroDataProvider(db_conn)
        latest = provider.get_latest('cbe_rate')
        context = provider.get_macro_regime_context()
    """

    def __init__(self, db):
        self.db = db
        self._ensure_table()

    def _ph(self, n: int) -> str:
        return f'${n}' if DATABASE_URL else '?'

    def _now(self) -> str:
        return 'NOW()' if DATABASE_URL else "datetime('now')"

    def _ensure_table(self):
        """Create macro_indicators table if it doesn't exist."""
        try:
            cursor = self.db.cursor()
            auto_id = 'SERIAL PRIMARY KEY' if DATABASE_URL else 'INTEGER PRIMARY KEY AUTOINCREMENT'
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS macro_indicators (
                    id {auto_id},
                    indicator TEXT NOT NULL,
                    value REAL NOT NULL,
                    period TEXT NOT NULL,
                    source TEXT NOT NULL,
                    fetched_at TIMESTAMP DEFAULT {self._now()}
                )
            """)
            self.db.commit()
        except Exception as e:
            logger.debug(f"macro_indicators table create: {e}")

    def get_latest(self, indicator: str) -> dict:
        """
        Returns latest value for an indicator.
        Returns: {'value': float, 'period': str, 'source': str, 'fetched_at': str}
        """
        try:
            cursor = self.db.cursor()
            if DATABASE_URL:
                cursor.execute("""
                    SELECT value, period, source, fetched_at
                    FROM macro_indicators
                    WHERE indicator = $1
                    ORDER BY fetched_at DESC LIMIT 1
                """, (indicator,))
            else:
                cursor.execute("""
                    SELECT value, period, source, fetched_at
                    FROM macro_indicators
                    WHERE indicator = ?
                    ORDER BY fetched_at DESC LIMIT 1
                """, (indicator,))

            row = cursor.fetchone()
            if row:
                rec = row if isinstance(row, dict) else dict(zip(
                    ['value', 'period', 'source', 'fetched_at'],
                    row
                ))
                return rec

        except Exception as e:
            logger.debug(f"get_latest({indicator}): {e}")

        # Return default
        default = _DEFAULTS.get(indicator, {'value': 0, 'period': 'N/A', 'source': 'default'})
        return {**default, 'fetched_at': None}

    def get_series(self, indicator: str, periods: int = 12) -> list:
        """Returns last N periods for trend analysis."""
        try:
            cursor = self.db.cursor()
            if DATABASE_URL:
                cursor.execute("""
                    SELECT value, period, source, fetched_at
                    FROM macro_indicators
                    WHERE indicator = $1
                    ORDER BY period DESC LIMIT $2
                """, (indicator, periods))
            else:
                cursor.execute("""
                    SELECT value, period, source, fetched_at
                    FROM macro_indicators
                    WHERE indicator = ?
                    ORDER BY period DESC LIMIT ?
                """, (indicator, periods))

            cols = ['value', 'period', 'source', 'fetched_at']
            rows = cursor.fetchall() or []
            return [row if isinstance(row, dict) else dict(zip(cols, row)) for row in rows]

        except Exception as e:
            logger.debug(f"get_series({indicator}): {e}")
            return []

    async def refresh_all(self) -> dict:
        """
        Fetches all indicators from available sources.
        Returns {indicator: success_bool}.

        Sources:
          - USD/EGP: yfinance (EGP=X)
          - CBE rate: manual/config (CBE doesn't publish via API)
          - CPI/GDP: manual (World Bank has significant lag)
        """
        results = {}

        # USD/EGP via yfinance
        results['usd_egp'] = await self._refresh_usd_egp()

        # CBE rate — use existing collect_data.py _fetch_usdegp_rate or manual
        results['cbe_rate'] = self._refresh_from_default('cbe_rate')

        # CPI/GDP — these lag months behind, use defaults
        results['cpi_yoy'] = self._refresh_from_default('cpi_yoy')
        results['gdp_growth'] = self._refresh_from_default('gdp_growth')

        return results

    async def _refresh_usd_egp(self) -> bool:
        """Fetch USD/EGP rate from yfinance."""
        try:
            import yfinance as yf
            ticker = yf.Ticker('EGP=X')
            hist = ticker.history(period='5d')
            if hist is not None and not hist.empty:
                rate = float(hist['Close'].iloc[-1])
                period = datetime.now().strftime('%Y-%m')
                self._upsert(indicator='usd_egp', value=rate, period=period, source='yfinance')
                logger.info(f"USD/EGP refreshed: {rate:.2f}")
                return True
        except Exception as e:
            logger.warning(f"USD/EGP refresh failed: {e}")
        return False

    def _refresh_from_default(self, indicator: str) -> bool:
        """Store default value if no recent data exists."""
        try:
            latest = self.get_latest(indicator)
            if latest.get('fetched_at') is not None:
                return True  # Already have data

            default = _DEFAULTS.get(indicator)
            if default:
                self._upsert(
                    indicator=indicator,
                    value=default['value'],
                    period=default['period'],
                    source=default['source'],
                )
                return True
        except Exception as e:
            logger.debug(f"Default refresh for {indicator}: {e}")
        return False

    def _upsert(self, indicator: str, value: float, period: str, source: str):
        """Insert or update a macro indicator."""
        try:
            cursor = self.db.cursor()
            if DATABASE_URL:
                cursor.execute("""
                    INSERT INTO macro_indicators (indicator, value, period, source, fetched_at)
                    VALUES ($1, $2, $3, $4, NOW())
                """, (indicator, value, period, source))
            else:
                cursor.execute("""
                    INSERT INTO macro_indicators (indicator, value, period, source, fetched_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (indicator, value, period, source))
            self.db.commit()
        except Exception as e:
            logger.warning(f"Macro upsert failed for {indicator}: {e}")

    def get_macro_regime_context(self) -> dict:
        """
        Returns composite macro context for simulation engine.

        Returns:
            {
                'rate_environment': 'high' | 'normal' | 'low',
                'fx_stress': bool,
                'inflation_regime': 'high' | 'moderate' | 'low',
                'growth_momentum': 'positive' | 'negative',
                'macro_risk_score': float,  # 0.0–1.0 composite
            }
        """
        cbe = self.get_latest('cbe_rate')
        usd_egp = self.get_latest('usd_egp')
        cpi = self.get_latest('cpi_yoy')
        gdp = self.get_latest('gdp_growth')

        # Rate environment
        rate = cbe.get('value', 27.25)
        if rate > 18:
            rate_env = 'high'
        elif rate > 12:
            rate_env = 'normal'
        else:
            rate_env = 'low'

        # FX stress: check if EGP depreciated >5% recently
        # (We only have point-in-time, so compare against a baseline)
        fx_rate = usd_egp.get('value', 50.0)
        fx_stress = fx_rate > 52.0  # Rough threshold for Q2 2026

        # Inflation regime
        inflation = cpi.get('value', 13.6)
        if inflation > 20:
            inflation_regime = 'high'
        elif inflation > 10:
            inflation_regime = 'moderate'
        else:
            inflation_regime = 'low'

        # Growth momentum
        growth = gdp.get('value', 3.5)
        growth_momentum = 'positive' if growth > 0 else 'negative'

        # Composite risk score (0.0 = low risk, 1.0 = high risk)
        risk_components = []
        risk_components.append(0.4 if rate_env == 'high' else (0.2 if rate_env == 'normal' else 0.0))
        risk_components.append(0.3 if fx_stress else 0.0)
        risk_components.append(0.2 if inflation_regime == 'high' else (0.1 if inflation_regime == 'moderate' else 0.0))
        risk_components.append(0.1 if growth_momentum == 'negative' else 0.0)
        macro_risk_score = min(1.0, sum(risk_components))

        return {
            'rate_environment': rate_env,
            'fx_stress': fx_stress,
            'inflation_regime': inflation_regime,
            'growth_momentum': growth_momentum,
            'macro_risk_score': round(macro_risk_score, 2),
            'indicators': {
                'cbe_rate': rate,
                'usd_egp': fx_rate,
                'cpi_yoy': inflation,
                'gdp_growth': growth,
            },
        }
