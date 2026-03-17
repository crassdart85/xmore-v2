"""
engines/etf_rag_embedding_worker.py — Process PENDING rag_embedding_job rows.

For each pending job:
  1. Load PDF from storage_uri (pdfplumber)
  2. Chunk text (500 chars, 50 overlap)
  3. Embed each chunk via Gemini text-embedding-005
  4. Upsert into rag_chunks (source_type='etf_document')
  5. Update rag_embedding_job → SUCCESS or FAILED

Run:
    python -m engines.etf_rag_embedding_worker
"""

import os
import sys
import time
import json
import logging
from datetime import datetime

import requests

from database import create_tables, get_connection, _adapt_sql

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50
RATE_LIMIT_MS = 130  # ms between Gemini API calls (stay under 10 req/s free tier)


def _chunk_text(text: str) -> list:
    if not text or not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _gemini_embed(text: str) -> list | None:
    """Call Gemini text-embedding-005 API. Returns float list or None."""
    if not GOOGLE_API_KEY:
        logger.warning('[etf_rag_embedding_worker] GOOGLE_API_KEY not set')
        return None
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'text-embedding-005:embedContent?key={GOOGLE_API_KEY}'
    )
    body = {'content': {'parts': [{'text': text}]}}
    try:
        resp = requests.post(url, json=body, timeout=20)
        if resp.status_code != 200:
            logger.warning('[etf_rag_embedding_worker] Embed API %s: %s', resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        return data.get('embedding', {}).get('values')
    except Exception as exc:
        logger.warning('[etf_rag_embedding_worker] Embed API error: %s', exc)
        return None


def _extract_pdf_text(storage_uri: str) -> str:
    """Extract text from a local PDF file using pdfplumber."""
    try:
        import pdfplumber
        with pdfplumber.open(storage_uri) as pdf:
            parts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
            return '\n'.join(parts)
    except Exception as exc:
        logger.warning('[etf_rag_embedding_worker] PDF extract failed for %s: %s', storage_uri, exc)
        return ''


def _upsert_chunk(conn, is_pg: bool, doc_id: int, idx: int, chunk: str,
                  embedding: list, source_meta: dict):
    ph = '%s' if is_pg else '?'
    emb_json  = json.dumps(embedding)
    meta_json = json.dumps(source_meta)
    if is_pg:
        vec_str = '[' + ','.join(str(v) for v in embedding) + ']'
        try:
            conn.cursor().execute(f"""
                INSERT INTO rag_chunks
                  (source_type, source_id, chunk_index, chunk_text, embedding, source_meta, embedding_vec)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph}::vector)
                ON CONFLICT (source_type, source_id, chunk_index)
                DO UPDATE SET chunk_text=EXCLUDED.chunk_text,
                              embedding=EXCLUDED.embedding,
                              source_meta=EXCLUDED.source_meta,
                              embedding_vec=EXCLUDED.embedding_vec
            """, ('etf_document', doc_id, idx, chunk, emb_json, meta_json, vec_str))
            return
        except Exception:
            pass
        conn.cursor().execute(f"""
            INSERT INTO rag_chunks
              (source_type, source_id, chunk_index, chunk_text, embedding, source_meta)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph})
            ON CONFLICT (source_type, source_id, chunk_index)
            DO UPDATE SET chunk_text=EXCLUDED.chunk_text,
                          embedding=EXCLUDED.embedding,
                          source_meta=EXCLUDED.source_meta
        """, ('etf_document', doc_id, idx, chunk, emb_json, meta_json))
    else:
        conn.cursor().execute(f"""
            INSERT OR REPLACE INTO rag_chunks
              (source_type, source_id, chunk_index, chunk_text, embedding, source_meta)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph})
        """, ('etf_document', doc_id, idx, chunk, emb_json, meta_json))


def run():
    if not GOOGLE_API_KEY:
        logger.warning('[etf_rag_embedding_worker] GOOGLE_API_KEY not set — skipping')
        return 0

    is_pg = bool(os.getenv('DATABASE_URL'))
    ph = '%s' if is_pg else '?'

    with get_connection() as conn:
        cur = conn.cursor()
        if is_pg:
            cur.execute("""
                SELECT j.job_id, j.doc_id, d.storage_uri, d.title, d.url, d.doc_type, i.symbol
                FROM rag_embedding_job j
                JOIN rag_document d ON d.doc_id = j.doc_id
                LEFT JOIN instrument i ON i.instrument_id = d.instrument_id
                WHERE j.status = 'PENDING'
                ORDER BY j.job_id
            """)
        else:
            cur.execute("""
                SELECT j.id, j.doc_id, d.storage_uri, d.title, d.url, d.doc_type, i.symbol
                FROM rag_embedding_job j
                JOIN rag_document d ON d.id = j.doc_id
                LEFT JOIN instrument i ON i.id = d.instrument_id
                WHERE j.status = 'PENDING'
                ORDER BY j.id
            """)
        jobs = cur.fetchall()

    if not jobs:
        logger.info('[etf_rag_embedding_worker] No pending embedding jobs')
        return 0

    logger.info('[etf_rag_embedding_worker] Processing %d jobs…', len(jobs))
    completed = 0

    for job in jobs:
        if hasattr(job, 'keys'):
            job_id       = job.get('job_id') or job.get('id')
            doc_id       = job['doc_id']
            storage_uri  = job.get('storage_uri')
            title        = job.get('title', '')
            url          = job.get('url', '')
            doc_type     = job.get('doc_type', '')
            symbol       = job.get('symbol', '')
        else:
            job_id, doc_id, storage_uri, title, url, doc_type, symbol = job

        if not storage_uri:
            logger.warning('[etf_rag_embedding_worker] job %s has no storage_uri — skip', job_id)
            continue

        # Mark as RUNNING
        with get_connection() as conn:
            id_col = 'job_id' if is_pg else 'id'
            conn.cursor().execute(_adapt_sql(
                f"UPDATE rag_embedding_job SET status='RUNNING', started_at={'NOW()' if is_pg else 'CURRENT_TIMESTAMP'} WHERE {id_col}={ph}"
            ), (job_id,))

        text = _extract_pdf_text(storage_uri)
        if not text.strip():
            with get_connection() as conn:
                id_col = 'job_id' if is_pg else 'id'
                conn.cursor().execute(_adapt_sql(
                    f"UPDATE rag_embedding_job SET status='FAILED', error_message={ph}, finished_at={'NOW()' if is_pg else 'CURRENT_TIMESTAMP'} WHERE {id_col}={ph}"
                ), ('No text extracted from PDF', job_id))
            continue

        chunks = _chunk_text(text)
        source_meta = {'title': title, 'url': url, 'doc_type': doc_type, 'symbol': symbol or ''}
        errors = 0

        with get_connection() as conn:
            for idx, chunk in enumerate(chunks):
                embedding = _gemini_embed(chunk)
                if embedding is None:
                    errors += 1
                    continue
                try:
                    _upsert_chunk(conn, is_pg, doc_id, idx, chunk, embedding, source_meta)
                except Exception as exc:
                    logger.warning('[etf_rag_embedding_worker] chunk %d for doc %s: %s', idx, doc_id, exc)
                    errors += 1
                if idx < len(chunks) - 1:
                    time.sleep(RATE_LIMIT_MS / 1000)

        final_status = 'SUCCESS' if errors == 0 else ('FAILED' if errors == len(chunks) else 'SUCCESS')
        err_msg = f'{errors}/{len(chunks)} chunks failed' if errors > 0 else None

        with get_connection() as conn:
            id_col = 'job_id' if is_pg else 'id'
            conn.cursor().execute(_adapt_sql(
                f"UPDATE rag_embedding_job SET status={ph}, error_message={ph}, finished_at={'NOW()' if is_pg else 'CURRENT_TIMESTAMP'} WHERE {id_col}={ph}"
            ), (final_status, err_msg, job_id))

        logger.info('[etf_rag_embedding_worker] doc %s (%s): %d/%d chunks embedded — %s',
                    doc_id, title[:40], len(chunks) - errors, len(chunks), final_status)
        if final_status == 'SUCCESS':
            completed += 1

    logger.info('[etf_rag_embedding_worker] Done — %d/%d jobs completed', completed, len(jobs))
    return completed


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_rag_embedding_worker', 'success', f'{count} jobs', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_rag_embedding_worker] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_rag_embedding_worker', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
