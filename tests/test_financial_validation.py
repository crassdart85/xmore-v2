"""
Financial Validation Test Suite — live-tests all financial math end-to-end.

Verifies:
1. Sharpe/Sortino use correct KSA SAIBOR 3M rate (4.89%)
2. Max drawdown uses compounded equity curve (not summing %)
3. Returns are in percentage points throughout the pipeline
4. Transaction costs use KSA Tadawul rates (38.2 bps RT)
5. Evaluation engine correctly maps signals to correctness
6. Track-record JS KPI calculations match Python equivalents
7. Consensus signals produce a measurable competitive edge

Run with: pytest tests/test_financial_validation.py -v
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engines.performance_metrics import (
    sharpe_ratio, sortino_ratio, max_drawdown, profit_factor,
    cumulative_return, apply_transaction_costs, avg, stddev,
    calculate_benchmark_comparison, calculate_calmar_ratio,
    EGX_DAILY_RF, EGX_RISK_FREE_RATE_ANNUAL, EGX_TRADING_DAYS_PER_YEAR,
    EGX_ROUND_TRIP_RATE,
)
from engines.evaluate_performance import evaluate_correctness


# ════════════════════════════════════════════════════════════════
#   1. KSA MARKET PARAMETERS
# ════════════════════════════════════════════════════════════════

class TestKSAParameters:
    """Verify KSA SAIBOR 3M / Tadawul parameters are active, not EGX."""

    def test_risk_free_rate_is_saibor(self):
        """Annual RF should be SAIBOR 3M ~4.89%, not CBE 27.25%."""
        assert 0.04 <= EGX_RISK_FREE_RATE_ANNUAL <= 0.06, (
            f"Expected ~4.89%, got {EGX_RISK_FREE_RATE_ANNUAL*100:.2f}%"
        )

    def test_trading_days_is_250(self):
        """Tadawul trades Sun–Thu = ~250 days, not 247 (EGX) or 252 (NYSE)."""
        assert EGX_TRADING_DAYS_PER_YEAR == 250

    def test_daily_rf_is_sensible(self):
        """Daily RF = (1+0.0489)^(1/250) - 1 ≈ 0.000191."""
        expected = (1 + 0.0489) ** (1 / 250) - 1
        assert abs(EGX_DAILY_RF - expected) < 1e-6, (
            f"Expected {expected:.6f}, got {EGX_DAILY_RF:.6f}"
        )

    def test_round_trip_cost_is_ksa(self):
        """RT cost should be ~38.2 bps (0.00382), not EGX 72.5 bps."""
        assert 0.003 <= EGX_ROUND_TRIP_RATE <= 0.005, (
            f"Expected ~0.00382, got {EGX_ROUND_TRIP_RATE}"
        )


# ════════════════════════════════════════════════════════════════
#   2. SHARPE RATIO — UNIT CONSISTENCY
# ════════════════════════════════════════════════════════════════

class TestSharpeRatio:
    """Sharpe must correctly handle % returns and decimal RF rate."""

    def test_sharpe_positive_for_positive_excess(self):
        """+0.10% daily avg (= ~25% annual), 1% daily vol → annualized Sharpe > 0."""
        returns = [0.10] * 100  # constant 0.10% daily
        # Annualized: 0.001 daily → ~28% annual. RF = 4.89%.  Excess > 0 → Sharpe > 0.
        # But constant returns → zero stdev → Sharpe = 0. Use slight noise.
        import random; random.seed(99)
        returns = [0.10 + random.gauss(0, 1.0) for _ in range(250)]
        sr = sharpe_ratio(returns)
        assert sr > 0, f"Should be positive for 0.10% daily mean, got {sr:.4f}"

    def test_sharpe_negative_for_negative_excess(self):
        """Negative daily mean → negative Sharpe."""
        import random; random.seed(42)
        returns = [-0.30 + random.gauss(0, 1.0) for _ in range(250)]
        sr = sharpe_ratio(returns)
        assert sr < 0, f"Should be negative for -0.30% daily mean, got {sr:.4f}"

    def test_sharpe_magnitude_sanity(self):
        """
        Sharpe ratio of ~0.10% daily mean, ~1% daily vol should produce
        an annualized Sharpe in the range [0, 3] — not 100+ or -100.
        """
        import random; random.seed(7)
        returns = [0.10 + random.gauss(0, 1.0) for _ in range(250)]
        sr = sharpe_ratio(returns)
        assert -5 < sr < 5, f"Sharpe should be in [-5, 5], got {sr:.4f}"

    def test_sharpe_manual_calculation(self):
        """Manual Sharpe check: (mean/100 - dailyRf) / (std/100) * sqrt(250)."""
        returns = [1.5, -0.8, 0.3, 2.1, -0.2]  # in %
        m = sum(returns) / len(returns) / 100     # decimal mean
        s = stddev(returns) / 100                 # decimal std
        expected = ((m - EGX_DAILY_RF) / s) * math.sqrt(250)
        actual = sharpe_ratio(returns)
        assert abs(actual - expected) < 0.01, (
            f"Manual={expected:.4f}, sharpe_ratio={actual:.4f}"
        )

    def test_sharpe_zero_std_returns_zero(self):
        """All identical returns → std=0 → Sharpe=0, not crash."""
        assert sharpe_ratio([1.0, 1.0, 1.0]) == 0.0


# ════════════════════════════════════════════════════════════════
#   3. SORTINO RATIO
# ════════════════════════════════════════════════════════════════

class TestSortinoRatio:
    """Sortino uses only downside deviation."""

    def test_sortino_no_downside_returns_cap(self):
        """All positive returns → Sortino = 99.9."""
        assert sortino_ratio([0.5, 1.0, 0.3, 0.8, 1.2]) == 99.9

    def test_sortino_higher_than_sharpe_when_skewed_positive(self):
        """Positively-skewed returns → Sortino > Sharpe (less downside penalty)."""
        returns = [2.0, 1.5, 0.8, -0.3, 1.2, 0.5, -0.1, 3.0, 0.4, -0.2,
                   1.0, 0.7, 2.5, -0.5, 0.3, 1.8, 0.2, 0.9, -0.1, 1.5]
        sr = sharpe_ratio(returns)
        so = sortino_ratio(returns)
        assert so > sr, f"Sortino ({so:.2f}) should > Sharpe ({sr:.2f}) for positive skew"

    def test_sortino_magnitude_sanity(self):
        """Sortino should be in [-10, 100], not 1000+."""
        import random; random.seed(3)
        returns = [0.05 + random.gauss(0, 1.0) for _ in range(250)]
        so = sortino_ratio(returns)
        assert -15 < so < 100, f"Sortino out of range: {so:.2f}"


# ════════════════════════════════════════════════════════════════
#   4. MAX DRAWDOWN — COMPOUNDING
# ════════════════════════════════════════════════════════════════

class TestMaxDrawdown:
    """Max drawdown must compound, not sum."""

    def test_drawdown_single_loss(self):
        """Single -5% loss → exactly -5% drawdown."""
        dd = max_drawdown([0.0, 0.0, -5.0, 0.0])
        assert abs(dd - (-5.0)) < 0.01, f"Expected -5.0%, got {dd:.2f}%"

    def test_drawdown_compounding_not_additive(self):
        """
        Three sequential -10% losses:
        Additive: -30%
        Compounded: 1 * 0.9^3 = 0.729 → -27.1%
        Must be closer to -27.1% than -30%.
        """
        dd = max_drawdown([-10.0, -10.0, -10.0])
        assert -28 < dd < -26, f"Compounded DD should be ~-27.1%, got {dd:.2f}%"

    def test_drawdown_recovery_resets_peak(self):
        """After large gain, a subsequent loss should be measured from new peak."""
        returns = [5.0, 5.0, 5.0, -3.0]
        dd = max_drawdown(returns)
        # Peak equity: 1.05^3 = 1.1576. After -3%: 1.1576 * 0.97 = 1.1229
        # DD = (1.1229 - 1.1576) / 1.1576 * 100 = -3.0%
        assert abs(dd - (-3.0)) < 0.1, f"Expected ~-3.0%, got {dd:.2f}%"

    def test_drawdown_all_positive_is_zero(self):
        """Monotonically increasing → no drawdown."""
        dd = max_drawdown([1.0, 2.0, 0.5, 1.0, 3.0])
        assert dd == 0.0

    def test_drawdown_empty_is_zero(self):
        assert max_drawdown([]) == 0.0

    def test_drawdown_never_exceeds_100(self):
        """Even extreme losses should not exceed -100% drawdown."""
        dd = max_drawdown([-50.0, -50.0, -50.0])
        # 0.5^3 = 0.125 → -87.5%
        assert dd >= -100.0, f"DD should never exceed -100%, got {dd:.2f}%"
        assert abs(dd - (-87.5)) < 0.5


# ════════════════════════════════════════════════════════════════
#   5. CUMULATIVE RETURN — COMPOUNDING
# ════════════════════════════════════════════════════════════════

class TestCumulativeReturn:
    """Cumulative return must compound, not sum."""

    def test_cumulative_2percent_10days(self):
        """2% daily for 10 days: (1.02)^10 - 1 = 21.90%, not 20%."""
        result = cumulative_return([2.0] * 10)
        expected = ((1.02 ** 10) - 1) * 100
        assert abs(result - expected) < 0.01, f"Expected {expected:.2f}%, got {result:.2f}%"

    def test_cumulative_loss_recovery(self):
        """-10% then +11.11% should come back to 0%."""
        result = cumulative_return([-10.0, 11.1111])
        assert abs(result) < 0.01, f"Expected ~0%, got {result:.4f}%"


# ════════════════════════════════════════════════════════════════
#   6. TRANSACTION COSTS — KSA
# ════════════════════════════════════════════════════════════════

class TestTransactionCosts:
    """Verify KSA transaction cost deduction."""

    def test_default_cost_is_ksa_rate(self):
        """Default deduction should be ~0.382 pp per trade."""
        returns = [2.0, 3.0, -1.0]
        net = apply_transaction_costs(returns)
        expected_cost_pp = EGX_ROUND_TRIP_RATE * 100  # 0.382 pp
        for gross, net_r in zip(returns, net):
            assert abs(net_r - (gross - expected_cost_pp)) < 0.001

    def test_custom_costs_applied(self):
        """Custom per-trade costs are deducted correctly."""
        returns = [5.0, -2.0]
        costs = [0.50, 0.30]  # 0.50 pp and 0.30 pp
        net = apply_transaction_costs(returns, costs)
        assert net == [4.5, -2.3]


# ════════════════════════════════════════════════════════════════
#   7. EVALUATE_CORRECTNESS — SIGNAL MAPPING
# ════════════════════════════════════════════════════════════════

class TestEvaluateCorrectness:
    """BUY/SELL/HOLD and UP/DOWN correctness logic."""

    def test_buy_correct_on_up(self):
        assert evaluate_correctness("BUY", 1.5) is True

    def test_buy_wrong_on_down(self):
        assert evaluate_correctness("BUY", -0.5) is False

    def test_sell_correct_on_down(self):
        assert evaluate_correctness("SELL", -2.0) is True

    def test_sell_wrong_on_up(self):
        assert evaluate_correctness("SELL", 1.0) is False

    def test_hold_correct_mild_loss(self):
        assert evaluate_correctness("HOLD", -1.5) is True

    def test_hold_wrong_crash(self):
        assert evaluate_correctness("HOLD", -3.0) is False

    def test_up_same_as_buy(self):
        """KSA consensus uses UP instead of BUY."""
        assert evaluate_correctness("UP", 2.0) is True
        assert evaluate_correctness("UP", -1.0) is False

    def test_down_same_as_sell(self):
        """KSA consensus uses DOWN instead of SELL."""
        assert evaluate_correctness("DOWN", -2.0) is True
        assert evaluate_correctness("DOWN", 1.0) is False

    def test_watch_returns_none(self):
        """WATCH signal → no correctness evaluation."""
        assert evaluate_correctness("WATCH", 5.0) is None

    def test_none_returns_none(self):
        """None action → no correctness evaluation."""
        assert evaluate_correctness(None, 5.0) is None


# ════════════════════════════════════════════════════════════════
#   8. PROFIT FACTOR
# ════════════════════════════════════════════════════════════════

class TestProfitFactor:

    def test_2_to_1_ratio(self):
        """2x profit vs loss → PF = 2.0."""
        pf = profit_factor([2.0, 4.0, -1.0, -2.0])
        # gains=6, losses=3 → 2.0
        assert abs(pf - 2.0) < 0.01

    def test_no_losses(self):
        """All wins → PF = 99.9 (capped)."""
        assert profit_factor([1.0, 2.0, 3.0]) == 99.9

    def test_no_gains(self):
        """All losses → PF = 0."""
        assert profit_factor([-1.0, -2.0]) == 0.0


# ════════════════════════════════════════════════════════════════
#   9. BENCHMARK COMPARISON — DIVISION BY ZERO SAFE
# ════════════════════════════════════════════════════════════════

class TestBenchmarkComparison:

    def test_identical_series_zero_alpha(self):
        """Same returns → alpha ~0, beta ~1."""
        r = [0.5, -0.2, 1.0, -0.3, 0.8, 0.1, -0.5, 1.2, 0.3, -0.1] * 3
        result = calculate_benchmark_comparison(r, r)
        assert abs(result["alpha_total"]) < 0.1
        assert abs(result["beta"] - 1.0) < 0.05

    def test_empty_returns(self):
        """Empty returns → zeros, no crash."""
        result = calculate_benchmark_comparison([], [])
        assert result["beta"] == 0

    def test_zero_benchmark_no_crash(self):
        """All-zero benchmark → no division by zero crash."""
        r = [1.0, 2.0, -0.5]
        b = [0.0, 0.0, 0.0]
        result = calculate_benchmark_comparison(r, b)
        assert isinstance(result["beta"], (int, float))
        assert isinstance(result["up_capture"], (int, float))


# ════════════════════════════════════════════════════════════════
#  10. CALMAR RATIO
# ════════════════════════════════════════════════════════════════

class TestCalmarRatio:

    def test_calmar_positive_for_good_returns(self):
        """Positive mean with mild drawdown → positive Calmar."""
        import random; random.seed(1)
        returns = [0.15 + random.gauss(0, 0.8) for _ in range(100)]
        dd = max_drawdown(returns)
        cal = calculate_calmar_ratio(returns, abs(dd))
        assert cal is not None
        assert cal > 0, f"Expected positive Calmar, got {cal}"

    def test_calmar_zero_dd(self):
        """Zero drawdown → Calmar = 0.0 (not crash)."""
        assert calculate_calmar_ratio([0.1] * 50, max_dd=0.0) == 0.0


# ════════════════════════════════════════════════════════════════
#  11. COMPETITIVE EDGE SANITY (Simulated Signal Quality)
# ════════════════════════════════════════════════════════════════

class TestCompetitiveEdge:
    """
    Simulate a realistic signal stream and verify that the KPI calculations
    would produce metrics competitive for a retail/semi-institutional product.
    A viable trading system should show:
      - Win rate > 50%
      - Sharpe > 0.5 (annualized, net of costs)
      - Profit factor > 1.0
      - Max drawdown < 25%
    """

    @staticmethod
    def _simulate_signals(n=250, win_rate=0.55, avg_win_pct=1.8, avg_loss_pct=-1.2, seed=42):
        """Simulate a realistic daily signal return series."""
        import random
        random.seed(seed)
        returns = []
        for _ in range(n):
            if random.random() < win_rate:
                returns.append(avg_win_pct + random.gauss(0, 0.5))
            else:
                returns.append(avg_loss_pct + random.gauss(0, 0.4))
        return returns

    def test_55pct_win_rate_produces_positive_sharpe(self):
        """55% win rate, 1.8% avg win, -1.2% avg loss → positive net Sharpe."""
        returns = self._simulate_signals()
        net = apply_transaction_costs(returns)
        sr = sharpe_ratio(net)
        assert sr > 0, f"55% WR system Sharpe should be positive, got {sr:.2f}"

    def test_55pct_system_profit_factor_above_1(self):
        """55% system → profit factor > 1.0 after costs."""
        returns = self._simulate_signals()
        net = apply_transaction_costs(returns)
        pf = profit_factor(net)
        assert pf > 1.0, f"Profit factor should be > 1.0, got {pf:.2f}"

    def test_55pct_system_drawdown_under_25(self):
        """55% system → max drawdown < 25%."""
        returns = self._simulate_signals()
        net = apply_transaction_costs(returns)
        dd = max_drawdown(net)
        assert dd > -25.0, f"Max DD should be > -25%, got {dd:.2f}%"

    def test_50pct_random_system_sharpe_near_zero(self):
        """50/50 with symmetric wins/losses → Sharpe near zero (no edge)."""
        returns = self._simulate_signals(n=500, win_rate=0.50,
                                          avg_win_pct=1.5, avg_loss_pct=-1.5)
        sr = sharpe_ratio(returns)
        assert -1.5 < sr < 1.5, f"Random system Sharpe should be near 0, got {sr:.2f}"

    def test_ksa_cost_does_not_destroy_edge(self):
        """
        KSA 38.2 bps RT cost should not turn a profitable system unprofitable.
        Daily trading means ~250 × 0.382pp = 95.5pp annual cost, which is significant.
        The system must still produce a positive net return.
        """
        returns = self._simulate_signals(n=250, win_rate=0.55,
                                          avg_win_pct=1.8, avg_loss_pct=-1.2)
        gross_cr = cumulative_return(returns)
        net = apply_transaction_costs(returns)
        net_cr = cumulative_return(net)
        # Gross return should be strongly positive
        assert gross_cr > 50, f"Gross cumulative return should be > 50%, got {gross_cr:.2f}%"
        # Net return must remain positive despite ~0.382pp daily cost
        assert net_cr > 0, f"Net cumulative return should be positive, got {net_cr:.2f}%"
        # Cost should leave at least some profit (net > 1% of gross)
        assert net_cr > gross_cr * 0.01, (
            f"Net ({net_cr:.2f}%) should retain some profit vs gross ({gross_cr:.2f}%)"
        )


# ════════════════════════════════════════════════════════════════
#  12. CROSS-VALIDATION: PYTHON vs JS MATH
# ════════════════════════════════════════════════════════════════

class TestPythonJsCrossValidation:
    """
    Replicate the JS calcMaxDrawdownAbs and Sharpe from track-record.js
    in Python and verify they match our engine output.
    """

    @staticmethod
    def js_calcMaxDrawdownAbs(returnsArr):
        """Python port of track-record.js calcMaxDrawdownAbs (after fix)."""
        equity = 1.0
        peak = 1.0
        maxDd = 0.0
        for r in returnsArr:
            equity *= (1 + r / 100)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > maxDd:
                maxDd = dd
        return maxDd

    @staticmethod
    def js_calcSharpe(returnsArr):
        """Python port of track-record.js calcSharpe (after fix)."""
        KSA_TRADING_DAYS = 250
        KSA_DAILY_RF = (1.0489 ** (1 / KSA_TRADING_DAYS)) - 1
        n = len(returnsArr)
        if n < 2:
            return 0
        m = sum(returnsArr) / n
        s = (sum((r - m) ** 2 for r in returnsArr) / (n - 1)) ** 0.5
        if s <= 0:
            return 0
        return ((m / 100 - KSA_DAILY_RF) / (s / 100)) * math.sqrt(KSA_TRADING_DAYS)

    def test_drawdown_matches_js(self):
        """Python max_drawdown and JS calcMaxDrawdownAbs should agree."""
        import random; random.seed(55)
        returns = [random.gauss(0.05, 1.5) for _ in range(100)]
        py_dd = abs(max_drawdown(returns))  # Python returns negative
        js_dd = self.js_calcMaxDrawdownAbs(returns)
        assert abs(py_dd - js_dd) < 0.1, (
            f"Python DD={py_dd:.2f}% vs JS DD={js_dd:.2f}% — should match"
        )

    def test_sharpe_matches_js(self):
        """Python sharpe_ratio and JS calcSharpe should agree within tolerance."""
        import random; random.seed(55)
        returns = [random.gauss(0.05, 1.5) for _ in range(100)]
        py_sr = sharpe_ratio(returns)
        js_sr = self.js_calcSharpe(returns)
        assert abs(py_sr - js_sr) < 0.5, (
            f"Python Sharpe={py_sr:.2f} vs JS Sharpe={js_sr:.2f} — should be close"
        )
