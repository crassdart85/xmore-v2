"""Tests for DerivativesLogger audit trail.

1. Hash chain integrity after 10 pricing calls
2. Tamper detection: mutate result_json, verify_chain raises
3. Run ID linkage: every event has non-null linked_run_id
4. Round-trip serialisation: to_dict restores without data loss
"""
import json
import sqlite3
import tempfile
import uuid
import pytest
import numpy as np

from derivatives.models.bsm import BSMPricer
from derivatives.greeks.analytical import AnalyticalGreeks, Greeks
from derivatives.greeks.second_order import SecondOrderGreeks, SecondOrderGreeksCalculator
from derivatives.audit.derivatives_logger import DerivativesLogger, AuditFailureError
from derivatives.portfolio.var_integration import OptionsVaRResult


# ---------------------------------------------------------------------------
# Fixture: fresh in-memory logger per test
# ---------------------------------------------------------------------------

@pytest.fixture
def logger(tmp_path):
    db = str(tmp_path / "test_audit.db")
    return DerivativesLogger(db_path=db)


def _make_pricer():
    return BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")


def _make_run_id():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. Hash chain integrity after 10 pricing calls
# ---------------------------------------------------------------------------

def test_chain_intact_after_10_calls(logger):
    run_id = _make_run_id()
    pricer = _make_pricer()
    for _ in range(10):
        result = pricer.price()
        logger.log_pricing(pricer, result, run_id)

    assert logger.verify_chain() is True


def test_chain_intact_mixed_event_types(logger):
    """Chain holds across mixed pricing + Greeks + VaR events."""
    run_id = _make_run_id()
    pricer = _make_pricer()

    # Pricing
    for _ in range(3):
        logger.log_pricing(pricer, pricer.price(), run_id)

    # Greeks
    ag = AnalyticalGreeks(pricer)
    g = ag.compute()
    so = SecondOrderGreeksCalculator(pricer).compute()
    for _ in range(3):
        logger.log_greeks(g, so, run_id)

    # VaR
    var_res = OptionsVaRResult(
        var=0.05, cvar=0.08, method="delta_gamma",
        confidence=0.99, horizon_days=1,
        n_scenarios=1000, stressed_scenario=None
    )
    logger.log_var(var_res, run_id)

    assert logger.verify_chain() is True


# ---------------------------------------------------------------------------
# 2. Tamper detection
# ---------------------------------------------------------------------------

def test_tamper_detection_raises(logger):
    """Mutating result_json directly should cause verify_chain to raise."""
    run_id = _make_run_id()
    pricer = _make_pricer()

    for _ in range(5):
        logger.log_pricing(pricer, pricer.price(), run_id)

    # Directly mutate the third record's result_json in SQLite
    with sqlite3.connect(logger.db_path) as conn:
        rows = conn.execute(
            "SELECT event_id FROM derivatives_events ORDER BY recorded_at ASC"
        ).fetchall()
        target_event_id = rows[2][0]
        conn.execute(
            "UPDATE derivatives_events SET result_json = ? WHERE event_id = ?",
            ('{"price": 999.99, "tampered": true}', target_event_id),
        )

    with pytest.raises(AuditFailureError):
        logger.verify_chain()


def test_tamper_detection_on_prev_hash(logger):
    """Mutating prev_hash should also break verification."""
    run_id = _make_run_id()
    pricer = _make_pricer()

    for _ in range(4):
        logger.log_pricing(pricer, pricer.price(), run_id)

    with sqlite3.connect(logger.db_path) as conn:
        rows = conn.execute(
            "SELECT event_id FROM derivatives_events ORDER BY recorded_at ASC"
        ).fetchall()
        target = rows[-1][0]
        conn.execute(
            "UPDATE derivatives_events SET prev_hash = ? WHERE event_id = ?",
            ("a" * 64, target),
        )

    with pytest.raises(AuditFailureError):
        logger.verify_chain()


# ---------------------------------------------------------------------------
# 3. Run ID linkage
# ---------------------------------------------------------------------------

def test_linked_run_id_stored(logger):
    """Every event must record the run_id passed by the caller."""
    run_id = _make_run_id()
    pricer = _make_pricer()
    logger.log_pricing(pricer, pricer.price(), run_id)

    with sqlite3.connect(logger.db_path) as conn:
        rows = conn.execute(
            "SELECT linked_run_id FROM derivatives_events"
        ).fetchall()

    for row in rows:
        assert row[0] == run_id, f"linked_run_id mismatch: {row[0]} != {run_id}"


def test_linked_run_id_not_null(logger):
    """linked_run_id column must never be NULL."""
    run_id = _make_run_id()
    pricer = _make_pricer()

    for _ in range(5):
        logger.log_pricing(pricer, pricer.price(), run_id)

    with sqlite3.connect(logger.db_path) as conn:
        nulls = conn.execute(
            "SELECT COUNT(*) FROM derivatives_events WHERE linked_run_id IS NULL"
        ).fetchone()[0]

    assert nulls == 0


# ---------------------------------------------------------------------------
# 4. Round-trip serialisation
# ---------------------------------------------------------------------------

def test_greeks_round_trip():
    """Greeks as_dict() must be JSON-serialisable and lossless."""
    pricer = _make_pricer()
    g = AnalyticalGreeks(pricer).compute()
    d = g.as_dict()
    serialised = json.dumps(d)
    restored = json.loads(serialised)
    for k, v in d.items():
        assert abs(restored[k] - v) < 1e-12, f"Field {k} changed after serialisation"


def test_second_order_greeks_round_trip():
    pricer = _make_pricer()
    so = SecondOrderGreeksCalculator(pricer).compute()
    d = so.as_dict()
    serialised = json.dumps(d)
    restored = json.loads(serialised)
    for k, v in d.items():
        if v is not None and not (isinstance(v, float) and (v != v)):  # skip nan
            assert abs(restored[k] - v) < 1e-12


def test_var_result_round_trip():
    var_res = OptionsVaRResult(
        var=0.034, cvar=0.052, method="full_revaluation",
        confidence=0.99, horizon_days=1,
        n_scenarios=5000, stressed_scenario="vol_spike_50pct"
    )
    d = {
        "var": var_res.var, "cvar": var_res.cvar,
        "method": var_res.method, "confidence": var_res.confidence,
        "horizon_days": var_res.horizon_days, "n_scenarios": var_res.n_scenarios,
        "stressed_scenario": var_res.stressed_scenario,
    }
    restored = json.loads(json.dumps(d))
    assert restored["var"] == 0.034
    assert restored["stressed_scenario"] == "vol_spike_50pct"


# ---------------------------------------------------------------------------
# 5. Empty chain is valid
# ---------------------------------------------------------------------------

def test_empty_chain_valid(logger):
    assert logger.verify_chain() is True


# ---------------------------------------------------------------------------
# 6. verify_chain is standalone (no simulation required)
# ---------------------------------------------------------------------------

def test_verify_chain_standalone(tmp_path):
    """verify_chain must work without any active simulation run."""
    db = str(tmp_path / "standalone.db")
    logger = DerivativesLogger(db_path=db)

    pricer = _make_pricer()
    run_id = _make_run_id()
    for _ in range(5):
        logger.log_pricing(pricer, pricer.price(), run_id)

    # Create a brand-new logger pointing to same DB (no simulation context)
    standalone = DerivativesLogger(db_path=db)
    assert standalone.verify_chain() is True
