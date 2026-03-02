"""
engines/etf_docs_ingest.py — Download ETF PDFs and enqueue embedding jobs.

Seeds:
  - EGX30 ETF Information Sheet PDF
  - VanEck EGPT prospectus
  - Any rag_document rows with fetched_at IS NULL

Output:
  - rag_document (upsert on url)
  - rag_embedding_job (status=PENDING)

Run:
    python -m engines.etf_docs_ingest
"""

import os
import sys
import logging
import time
import hashlib
from datetime import date
from pathlib import Path

import requests

from database import create_tables, get_connection, _adapt_sql

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

STORAGE_DIR = Path(__file__).parent.parent / 'etf_docs'

# Seed list of known ETF documents
SEED_DOCS = [
    {
        'url':       'https://www.egx30etf.com/Content/PDF%20Files/EGX30%20ETF%20Information%20Sheet.pdf',
        'title':     'EGX30 ETF Information Sheet',
        'doc_type':  'INFO_SHEET',
        'publisher': 'EGX / Beltone',
        'language':  'en',
        'ticker':    'EGX30ETF',
        'exchange':  'EGX',
    },
    {
        'url':       'https://www.vaneck.com/us/en/library/market-vectors-etfs/egpt-statutory-prospectus-pdf/',
        'title':     'VanEck Egypt ETF (EGPT) Statutory Prospectus',
        'doc_type':  'PROSPECTUS',
        'publisher': 'VanEck',
        'language':  'en',
        'ticker':    'EGPT',
        'exchange':  'NYSE',
    },
]

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 Chrome/122.0 Safari/537.36'
    ),
}


def _download_pdf(url: str) -> tuple[bytes | None, str | None]:
    """Download a URL, return (bytes, content_hash) or (None, None) on failure."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30, allow_redirects=True)
        if resp.status_code != 200:
            logger.warning('[etf_docs_ingest] %s → HTTP %s', url, resp.status_code)
            return None, None
        content = resp.content
        content_hash = hashlib.sha256(content).hexdigest()
        return content, content_hash
    except Exception as exc:
        logger.warning('[etf_docs_ingest] download failed for %s: %s', url, exc)
        return None, None


def _get_instrument_id(conn, ticker: str, exchange: str):
    """Look up instrument_id for a ticker+exchange (or None if not found)."""
    is_pg = bool(os.getenv('DATABASE_URL'))
    ph = '%s' if is_pg else '?'
    cur = conn.cursor()
    cur.execute(_adapt_sql(f"SELECT {'instrument_id' if is_pg else 'id'} FROM instrument WHERE exchange={ph} AND symbol={ph}"),
                (exchange, ticker))
    row = cur.fetchone()
    if row is None:
        return None
    return row[0] if not hasattr(row, 'keys') else (row.get('instrument_id') or row.get('id'))


def _upsert_doc(conn, is_pg: bool, doc: dict, instrument_id, content_hash: str | None,
                storage_uri: str | None) -> int | None:
    """Upsert rag_document row, return doc_id."""
    ph = '%s' if is_pg else '?'
    cur = conn.cursor()
    if is_pg:
        cur.execute(f"""
            INSERT INTO rag_document
              (instrument_id, doc_type, title, publisher, language, url, content_hash, storage_uri, fetched_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph}, NOW())
            ON CONFLICT (url) DO UPDATE SET
              content_hash = EXCLUDED.content_hash,
              storage_uri  = EXCLUDED.storage_uri,
              fetched_at   = NOW()
            RETURNING doc_id
        """, (instrument_id, doc['doc_type'], doc['title'], doc.get('publisher'),
              doc.get('language', 'en'), doc['url'], content_hash, storage_uri))
        row = cur.fetchone()
        return row[0] if row else None
    else:
        cur.execute(f"""
            INSERT OR REPLACE INTO rag_document
              (instrument_id, doc_type, title, publisher, language, url, content_hash, storage_uri, fetched_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph}, CURRENT_TIMESTAMP)
        """, (instrument_id, doc['doc_type'], doc['title'], doc.get('publisher'),
              doc.get('language', 'en'), doc['url'], content_hash, storage_uri))
        cur.execute(f"SELECT id FROM rag_document WHERE url = {ph}", (doc['url'],))
        row = cur.fetchone()
        return row[0] if row else None


def _enqueue_embedding(conn, is_pg: bool, doc_id: int):
    """Insert a PENDING rag_embedding_job if one doesn't already exist."""
    ph = '%s' if is_pg else '?'
    cur = conn.cursor()
    # Only enqueue if no PENDING/RUNNING job already exists
    cur.execute(_adapt_sql(
        f"SELECT {'job_id' if is_pg else 'id'} FROM rag_embedding_job "
        f"WHERE doc_id={ph} AND status IN ('PENDING','RUNNING')"
    ), (doc_id,))
    if cur.fetchone():
        return
    if is_pg:
        cur.execute(f"INSERT INTO rag_embedding_job (doc_id) VALUES ({ph})", (doc_id,))
    else:
        cur.execute(f"INSERT INTO rag_embedding_job (doc_id) VALUES ({ph})", (doc_id,))


def run():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    is_pg = bool(os.getenv('DATABASE_URL'))

    # Collect docs to process: seeds + any unfetched rag_document rows
    docs_to_process = list(SEED_DOCS)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_adapt_sql(
            "SELECT {'doc_id' if is_pg else 'id'} AS id, url, title, doc_type FROM rag_document WHERE fetched_at IS NULL"
        ))
        for row in cur.fetchall():
            url = row['url'] if hasattr(row, 'keys') else row[1]
            title = row.get('title') if hasattr(row, 'keys') else row[2]
            doc_type = row.get('doc_type') if hasattr(row, 'keys') else row[3]
            docs_to_process.append({
                'url': url, 'title': title or url, 'doc_type': doc_type or 'OTHER',
                'ticker': None, 'exchange': None,
            })

    ingested = 0
    for doc in docs_to_process:
        url = doc['url']
        logger.info('[etf_docs_ingest] Downloading: %s', url)

        content, content_hash = _download_pdf(url)
        if content is None:
            logger.warning('[etf_docs_ingest] Skipping %s — download failed', url)
            continue

        # Save to local storage
        safe_name = url.split('/')[-1].split('?')[0][:80] or 'doc.pdf'
        filepath = STORAGE_DIR / safe_name
        filepath.write_bytes(content)
        storage_uri = str(filepath)

        with get_connection() as conn:
            inst_id = None
            if doc.get('ticker') and doc.get('exchange'):
                inst_id = _get_instrument_id(conn, doc['ticker'], doc['exchange'])

            doc_id = _upsert_doc(conn, is_pg, doc, inst_id, content_hash, storage_uri)
            if doc_id:
                _enqueue_embedding(conn, is_pg, doc_id)
                ingested += 1
                logger.info('[etf_docs_ingest] Ingested doc_id=%s: %s', doc_id, doc['title'])

        time.sleep(1)  # Polite delay between downloads

    logger.info('[etf_docs_ingest] Done — %d documents ingested', ingested)
    return ingested


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_docs_ingest', 'success', f'{count} docs', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_docs_ingest] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_docs_ingest', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
