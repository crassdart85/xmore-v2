"""
KSA Event Detector — scans recent news for high-impact events that should
trigger an immediate sentiment refresh for affected stocks.

Called at the START of run_agents.py / run_agents_ksa.py before generating
predictions. If high-impact events are detected, a targeted sentiment refresh
runs for affected symbols before the agent pipeline proceeds.

Usage:
    from engines.event_detector import EventDetector
    detector = EventDetector(db_conn)
    triggered = detector.scan_and_refresh()
    # triggered = [('2222.SR', 'earnings', 'immediate'), ...]
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')


def _ph(n: int) -> str:
    return f'${n}' if DATABASE_URL else '?'


class EventDetector:
    """
    Scans recent news articles for high-impact events that should trigger
    an immediate sentiment refresh for affected stocks.
    """

    EVENT_PATTERNS = {
        'sama_decision': {
            'keywords_en': [
                'SAMA', 'Saudi Central Bank', 'repo rate', 'reverse repo',
                'interest rate decision', 'monetary policy', 'SAIBOR',
            ],
            'keywords_ar': [
                'البنك المركزي السعودي', 'ساما', 'سعر الريبو', 'سعر الفائدة',
                'السياسة النقدية', 'سايبور',
            ],
            'affects': 'all',
            'urgency': 'immediate',
        },
        'earnings': {
            'keywords_en': [
                'quarterly results', 'annual results', 'net profit', 'revenue growth',
                'earnings per share', 'EPS', 'financial results', 'profit declined',
                'profit surged', 'dividend',
            ],
            'keywords_ar': [
                'نتائج مالية', 'صافي الربح', 'أرباح', 'إيرادات', 'توزيعات أرباح',
                'نتائج ربع سنوية', 'نتائج سنوية',
            ],
            'affects': 'mentioned_symbols',
            'urgency': 'immediate',
        },
        'regulatory': {
            'keywords_en': [
                'CMA', 'Capital Market Authority', 'Tadawul suspension',
                'trading halt', 'delisted', 'regulatory action',
            ],
            'keywords_ar': [
                'هيئة السوق المالية', 'وقف التداول', 'شطب', 'إجراء تنظيمي',
            ],
            'affects': 'mentioned_symbols',
            'urgency': 'immediate',
        },
        'index_rebalance': {
            'keywords_en': [
                'TASI rebalance', 'MT30 rebalance', 'index constituent', 'index review',
                'added to TASI', 'removed from TASI',
            ],
            'keywords_ar': [
                'مراجعة المؤشر', 'تعديل مكونات', 'إضافة للمؤشر',
            ],
            'affects': 'mentioned_symbols',
            'urgency': 'immediate',
        },
    }

    # Known Tadawul ticker patterns for extraction (e.g. 2222.SR)
    _TICKER_PATTERN = re.compile(r'\b(\d{4})\.SR\b')

    def __init__(self, db_conn):
        self.conn = db_conn

    def scan(self, lookback_hours: int = 6) -> List[Tuple[str, str, str]]:
        """
        Scan recent news for high-impact events.

        Returns: [(symbol, event_type, urgency), ...]
        """
        events = []
        articles = self._fetch_recent_articles(lookback_hours)

        if not articles:
            return events

        for article in articles:
            title = (article.get('title') or '').lower()
            content = (article.get('content') or article.get('description') or '').lower()
            text = f"{title} {content}"

            for event_type, pattern in self.EVENT_PATTERNS.items():
                matched = False

                # Check English keywords
                for kw in pattern['keywords_en']:
                    if kw.lower() in text:
                        matched = True
                        break

                # Check Arabic keywords
                if not matched:
                    for kw in pattern['keywords_ar']:
                        if kw in text:
                            matched = True
                            break

                if matched:
                    urgency = pattern['urgency']

                    if pattern['affects'] == 'all':
                        # CBE decisions affect all stocks
                        try:
                            from config.ksa_universe import KSA_STOCKS as ALL_STOCKS
                            for sym in ALL_STOCKS[:50]:  # Cap to avoid excessive refresh
                                events.append((sym, event_type, urgency))
                        except ImportError:
                            events.append(('ALL', event_type, urgency))
                    else:
                        # Extract mentioned symbols
                        symbols = self._extract_symbols(title + ' ' + content)
                        for sym in symbols:
                            events.append((sym, event_type, urgency))

        # Deduplicate
        seen = set()
        unique_events = []
        for ev in events:
            key = (ev[0], ev[1])
            if key not in seen:
                seen.add(key)
                unique_events.append(ev)

        return unique_events

    def scan_price_gaps(self, threshold_pct: float = 3.0) -> List[Tuple[str, str, str]]:
        """
        Detect significant opening price gaps (>threshold_pct vs prior close).
        """
        events = []
        try:
            cursor = self.conn.cursor()

            if DATABASE_URL:
                sql = """
                    SELECT p1.symbol,
                           p1.open as today_open,
                           p2.close as prev_close
                    FROM prices p1
                    JOIN prices p2 ON p1.symbol = p2.symbol
                    WHERE p1.date = (SELECT MAX(date) FROM prices)
                      AND p2.date = (SELECT MAX(date) FROM prices WHERE date < (SELECT MAX(date) FROM prices))
                      AND p2.close > 0
                      AND ABS((p1.open - p2.close) / p2.close) > $1
                """
                cursor.execute(sql, (threshold_pct / 100.0,))
            else:
                sql = """
                    SELECT p1.symbol,
                           p1.open as today_open,
                           p2.close as prev_close
                    FROM prices p1
                    JOIN prices p2 ON p1.symbol = p2.symbol
                    WHERE p1.date = (SELECT MAX(date) FROM prices)
                      AND p2.date = (SELECT MAX(date) FROM prices WHERE date < (SELECT MAX(date) FROM prices))
                      AND p2.close > 0
                      AND ABS((p1.open - p2.close) / p2.close) > ?
                """
                cursor.execute(sql, (threshold_pct / 100.0,))

            cols = [d[0] for d in cursor.description] if cursor.description else []
            for row in (cursor.fetchall() or []):
                rec = row if isinstance(row, dict) else dict(zip(cols, row))
                gap_pct = ((float(rec['today_open']) - float(rec['prev_close'])) / float(rec['prev_close'])) * 100
                events.append((rec['symbol'], 'price_gap', 'immediate'))
                logger.info(f"Price gap detected: {rec['symbol']} {gap_pct:+.1f}%")

        except Exception as e:
            logger.debug(f"Price gap scan failed: {e}")

        return events

    def scan_and_refresh(self, lookback_hours: int = 6) -> List[Tuple[str, str, str]]:
        """
        Full scan: news events + price gaps.
        If immediate events found, triggers targeted sentiment refresh.

        Returns list of detected events.
        """
        events = self.scan(lookback_hours)
        events.extend(self.scan_price_gaps())

        if not events:
            return events

        immediate = [e for e in events if e[2] == 'immediate']
        if not immediate:
            return events

        # Extract unique symbols needing refresh
        symbols = list(set(e[0] for e in immediate if e[0] != 'ALL'))
        if any(e[0] == 'ALL' for e in immediate):
            # CBE decision — refresh all
            try:
                from config import ALL_STOCKS
                symbols = ALL_STOCKS[:50]
            except ImportError:
                pass

        if symbols:
            logger.info(f"Event-triggered sentiment refresh for {len(symbols)} symbols: {symbols[:5]}...")
            try:
                from sentiment_gemini import collect_sentiment
                collect_sentiment(symbols=symbols, days_back=1)
            except Exception as e:
                logger.warning(f"Event-triggered sentiment refresh failed: {e}")

        return events

    def _fetch_recent_articles(self, lookback_hours: int = 6) -> list:
        """Fetch news articles from the last N hours."""
        try:
            cursor = self.conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime('%Y-%m-%d %H:%M:%S')

            if DATABASE_URL:
                cursor.execute("""
                    SELECT title, content, description, published_date
                    FROM news
                    WHERE published_date >= $1
                    ORDER BY published_date DESC
                    LIMIT 100
                """, (cutoff,))
            else:
                cursor.execute("""
                    SELECT title, content, description, published_date
                    FROM news
                    WHERE published_date >= ?
                    ORDER BY published_date DESC
                    LIMIT 100
                """, (cutoff,))

            cols = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall() or []
            return [row if isinstance(row, dict) else dict(zip(cols, row)) for row in rows]

        except Exception as e:
            logger.debug(f"Failed to fetch recent articles: {e}")
            return []

    def _extract_symbols(self, text: str) -> list:
        """Extract Tadawul ticker symbols from text."""
        # Direct ticker mentions (e.g. 2222.SR)
        tickers = self._TICKER_PATTERN.findall(text.upper())
        symbols = [f"{t}.SR" for t in tickers]

        # Also try to match known company names
        try:
            from config.ksa_universe import KSA_STOCKS
            for sym in KSA_STOCKS:
                base = sym.replace('.SR', '').lower()
                if base in text.lower() and sym not in symbols:
                    symbols.append(sym)
        except ImportError:
            pass

        return symbols[:20]  # Cap at 20 symbols per article
