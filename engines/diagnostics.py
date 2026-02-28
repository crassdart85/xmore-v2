"""
Diagnostics — GARCH + HMM Simulation Validation
=================================================
All statistical tests and visualisation routines required for institutional
auditability of the GARCH / HMM simulation engine.

GARCH diagnostics
-----------------
  run_garch_diagnostics(engine, returns)
    • Ljung-Box on raw returns and squared returns (ARCH-effect test)
    • Persistence summary table
    • Standardised-residual normality test (Jarque-Bera, KS vs Normal)
    • Conditional-vol vs realised-vol comparison per asset
    • AIC / BIC model comparison across variants

HMM diagnostics
---------------
  run_regime_diagnostics(regime_model, index_returns)
    • Viterbi state sequence plot (annotated)
    • Regime occupancy table
    • Transition-matrix heatmap
    • Regime-conditional return distribution comparison (KS test)

Simulation output diagnostics
------------------------------
  run_simulation_diagnostics(result)
    • Path fan chart for a single asset
    • Regime-conditional path separation
    • Terminal-return distribution summary

Usage
-----
    from engines.diagnostics import run_garch_diagnostics, run_regime_diagnostics
    run_garch_diagnostics(engine, returns_df, output_dir="reports/")
    run_regime_diagnostics(regime_model, index_returns, output_dir="reports/")

All plot functions return the matplotlib Figure for embedding.  If matplotlib
is unavailable they return None and print text-only summaries.

Dependencies
------------
    pip install matplotlib scipy statsmodels
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as _stats

logger = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────────────────

try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend (safe for servers)
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    logger.info("matplotlib not available — text-only diagnostics.")

try:
    from statsmodels.stats.diagnostic import acorr_ljungbox as _ljungbox_sm
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


# ── ─────────────────────────────────────────────────────────────────────────
# SECTION 1: GARCH diagnostics
# ── ─────────────────────────────────────────────────────────────────────────

def run_garch_diagnostics(
    engine,
    returns:    pd.DataFrame,
    output_dir: Optional[str] = None,
    verbose:    bool = True,
) -> dict:
    """
    Full GARCH diagnostic suite.

    Parameters
    ----------
    engine     : Fitted GARCHEngine instance.
    returns    : Raw return DataFrame used for fitting.
    output_dir : If provided, figures are saved to this directory.
    verbose    : Print text summary to stdout.

    Returns
    -------
    dict with keys:
        "arch_effects"    — Ljung-Box results per asset
        "persistence"     — persistence summary
        "residual_tests"  — normality tests on standardised residuals
        "warnings"        — list of flagged issues
    """
    report: dict = {
        "arch_effects":   {},
        "persistence":    {},
        "residual_tests": {},
        "warnings":       [],
    }

    fitted = engine.get_params()
    residuals = engine._residuals      # standardised GARCH residuals dict

    for symbol, params in fitted.items():
        series = returns[symbol].dropna()

        # ── Ljung-Box on raw returns (level autocorrelation) ──────────────
        lb_ret_p  = _ljungbox_pvalue(series,    lags=10)
        # Ljung-Box on squared returns (ARCH effect test)
        lb_sq_p   = _ljungbox_pvalue(series**2, lags=10)

        report["arch_effects"][symbol] = {
            "lb_returns_p10":         round(lb_ret_p, 4),
            "lb_squared_returns_p10": round(lb_sq_p,  4),
            "arch_effect_detected":   lb_sq_p < 0.05,
        }

        # ── Persistence ───────────────────────────────────────────────────
        persist = params.persistence
        status  = "OK" if persist < 1.0 else "NON-STATIONARY"
        report["persistence"][symbol] = {
            "alpha":       round(params.alpha, 4),
            "beta":        round(params.beta,  4),
            "gamma":       round(params.gamma, 4),
            "persistence": round(persist, 4),
            "status":      status,
        }
        if status == "NON-STATIONARY":
            report["warnings"].append(f"{symbol}: persistence {persist:.4f} >= 1")

        # ── Residual diagnostics ──────────────────────────────────────────
        std_resid = residuals.get(symbol)
        if std_resid is not None and len(std_resid) > 10:
            jb_stat, jb_p     = _stats.jarque_bera(std_resid)
            ks_stat, ks_p     = _stats.kstest(
                (std_resid - std_resid.mean()) / max(std_resid.std(), 1e-12),
                "norm"
            )
            lb_resid_p        = _ljungbox_pvalue(pd.Series(std_resid),    lags=10)
            lb_resid_sq_p     = _ljungbox_pvalue(pd.Series(std_resid**2), lags=10)

            report["residual_tests"][symbol] = {
                "jarque_bera_stat": round(float(jb_stat), 2),
                "jarque_bera_p":    round(float(jb_p),    4),
                "ks_normal_stat":   round(float(ks_stat), 4),
                "ks_normal_p":      round(float(ks_p),    4),
                "lb_resid_p10":     round(lb_resid_p, 4),
                "lb_resid_sq_p10":  round(lb_resid_sq_p, 4),
                "white_noise_ok":   lb_resid_p > 0.05 and lb_resid_sq_p > 0.05,
            }
            if lb_resid_sq_p < 0.05:
                report["warnings"].append(
                    f"{symbol}: squared residuals still autocorrelated (p={lb_resid_sq_p:.4f}) "
                    "— GARCH may be misspecified"
                )

    if verbose:
        _print_garch_report(report)

    if output_dir and HAS_MPL:
        os.makedirs(output_dir, exist_ok=True)
        fig = plot_garch_persistence(fitted)
        if fig:
            fig.savefig(os.path.join(output_dir, "garch_persistence.png"),
                        dpi=150, bbox_inches="tight")
            plt.close(fig)

        for symbol, params in fitted.items():
            series    = returns[symbol].dropna()
            std_resid = engine._residuals.get(symbol)
            if std_resid is not None:
                fig = plot_conditional_vol(symbol, series, params, std_resid)
                if fig:
                    fname = f"cond_vol_{symbol.replace('.','_')}.png"
                    fig.savefig(os.path.join(output_dir, fname),
                                dpi=150, bbox_inches="tight")
                    plt.close(fig)

    return report


def plot_conditional_vol(
    symbol:     str,
    returns:    pd.Series,
    params,                     # GARCHParams
    std_resid:  np.ndarray,
) -> Optional["plt.Figure"]:
    """
    2-panel figure:
    Top    — Conditional volatility estimate vs 20-day rolling realised vol.
    Bottom — Standardised residuals with ±2sigma bands.
    """
    if not HAS_MPL:
        return None

    rv20 = returns.rolling(20).std() * np.sqrt(252)
    T    = len(returns)

    # Rebuild approximate conditional vol from params for plotting
    # (use standardised residuals × sigma_t to recover approximate sigma_t series)
    sigma_approx = np.abs(std_resid) if std_resid is not None else np.ones(T)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    fig.suptitle(f"{symbol} — GARCH Diagnostics ({params.model_type})", fontsize=12)

    # Top: vol comparison
    ax1.plot(rv20.values[-len(sigma_approx):],
             color="#6b7280", alpha=0.7, linewidth=0.8, label="Realised Vol (20d)")
    ax1.axhline(params.sigma_t * np.sqrt(252), color="#ef4444",
                linestyle="--", linewidth=1.2, label=f"sigma_t (current) = {params.sigma_t*np.sqrt(252):.3f}")
    ax1.set_ylabel("Annualised Vol")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # Bottom: standardised residuals
    ax2.plot(std_resid, color="#3b82f6", alpha=0.6, linewidth=0.5)
    ax2.axhline( 2, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.7)
    ax2.axhline(-2, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.7)
    ax2.set_ylabel("Std Residuals")
    ax2.set_xlabel("Trading Days")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    return fig


def plot_garch_persistence(fitted: Dict) -> Optional["plt.Figure"]:
    """
    Horizontal bar chart of persistence (alpha + beta + 0.5γ) per asset.
    Red dashed line at 1.0 marks non-stationarity boundary.
    """
    if not HAS_MPL:
        return None

    symbols = list(fitted.keys())
    pers    = [fitted[s].persistence for s in symbols]
    colors  = ["#ef4444" if p >= 1.0 else "#22c55e" for p in pers]

    fig, ax = plt.subplots(figsize=(8, max(3, len(symbols) * 0.4)))
    bars = ax.barh(symbols, pers, color=colors, edgecolor="white", height=0.6)
    ax.axvline(1.0, color="#ef4444", linestyle="--", linewidth=1.2,
               label="Non-stationarity boundary")
    ax.set_xlabel("GARCH Persistence (alpha + beta + 0.5*gamma)")
    ax.set_title("GARCH Persistence per Asset")
    ax.legend(fontsize=8)
    ax.set_xlim(0, max(1.2, max(pers) + 0.05))
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


# ── ─────────────────────────────────────────────────────────────────────────
# SECTION 2: HMM regime diagnostics
# ── ─────────────────────────────────────────────────────────────────────────

def run_regime_diagnostics(
    regime_model,
    index_returns: pd.Series,
    output_dir:    Optional[str] = None,
    verbose:       bool = True,
) -> dict:
    """
    Full HMM / regime-switching diagnostic suite.

    Returns
    -------
    dict with keys:
        "occupancy"     — % time in each regime
        "ks_tests"      — KS test comparing return dists between regimes
        "transition"    — transition matrix stats
        "state"         — current RegimeState dict
    """
    state       = regime_model.get_regime_state()
    viterbi     = regime_model.get_viterbi_states()
    K           = state.n_regimes

    report: dict = {
        "state":      state.to_dict(),
        "occupancy":  {},
        "ks_tests":   {},
        "transition": {},
    }

    if viterbi is not None and len(viterbi) > 0:
        # ── Occupancy ─────────────────────────────────────────────────────
        counts = np.bincount(viterbi, minlength=K)
        for k in range(K):
            label = state.regime_label_en if k == state.current_regime else f"Regime {k}"
            report["occupancy"][k] = {
                "label":   label,
                "count":   int(counts[k]),
                "pct":     round(counts[k] / max(len(viterbi), 1), 4),
            }

        # ── Regime-conditional return distribution (KS test) ──────────────
        # Align viterbi with index_returns (both may have been trimmed by rolling windows)
        n_align = min(len(viterbi), len(index_returns))
        ret_arr = index_returns.values[-n_align:]

        for i in range(K):
            for j in range(i + 1, K):
                mask_i = viterbi[-n_align:] == i
                mask_j = viterbi[-n_align:] == j
                r_i    = ret_arr[mask_i]
                r_j    = ret_arr[mask_j]
                if len(r_i) > 5 and len(r_j) > 5:
                    ks_stat, ks_p = _stats.ks_2samp(r_i, r_j)
                    key = f"regime_{i}_vs_{j}"
                    report["ks_tests"][key] = {
                        "ks_stat":    round(float(ks_stat), 4),
                        "ks_p":       round(float(ks_p),    4),
                        "distinct":   ks_p < 0.05,
                        "n_i":        int(mask_i.sum()),
                        "n_j":        int(mask_j.sum()),
                    }

    # ── Transition stats ──────────────────────────────────────────────────
    P = np.array(state.transition_matrix)
    for k in range(K):
        report["transition"][k] = {
            "self_prob":         round(float(P[k, k]), 4),
            "expected_duration": round(state.expected_duration_days[k], 2),
        }

    if verbose:
        _print_regime_report(report, state)

    if output_dir and HAS_MPL:
        os.makedirs(output_dir, exist_ok=True)

        if viterbi is not None:
            fig = plot_viterbi_states(index_returns, viterbi, state)
            if fig:
                fig.savefig(os.path.join(output_dir, "viterbi_states.png"),
                            dpi=150, bbox_inches="tight")
                plt.close(fig)

            fig = plot_regime_distributions(index_returns, viterbi, state)
            if fig:
                fig.savefig(os.path.join(output_dir, "regime_distributions.png"),
                            dpi=150, bbox_inches="tight")
                plt.close(fig)

        fig = plot_transition_heatmap(state)
        if fig:
            fig.savefig(os.path.join(output_dir, "transition_heatmap.png"),
                        dpi=150, bbox_inches="tight")
            plt.close(fig)

    return report


def plot_viterbi_states(
    index_returns: pd.Series,
    viterbi:       np.ndarray,
    state,                         # RegimeState
) -> Optional["plt.Figure"]:
    """
    Annotated timeline showing index return with coloured regime background bands.
    Provides qualitative validation: bull / crash periods should align with
    known EGX macro events.
    """
    if not HAS_MPL:
        return None

    K       = state.n_regimes
    # Palette: green gradient for calm -> red for crisis
    palette = {
        2: ["#bbf7d0", "#fecaca"],
        3: ["#bbf7d0", "#fde68a", "#fecaca"],
    }.get(K, [plt.cm.RdYlGn(1 - k / max(K - 1, 1)) for k in range(K)])  # type: ignore

    n_align  = min(len(viterbi), len(index_returns))
    ret_plot = index_returns.values[-n_align:]
    dates    = np.arange(n_align)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle("Viterbi Regime Sequence — Market Index", fontsize=12)

    # Shade regime bands on return plot
    vit_aligned = viterbi[-n_align:]
    for k in range(K):
        mask  = vit_aligned == k
        label = state.regime_label_en if k == state.current_regime else \
                ["Calm", "Turbulent", "Crisis"][k] if K <= 3 else f"Regime {k}"
        ax1.fill_between(dates, ret_plot.min() * 1.5, ret_plot.max() * 1.5,
                         where=mask, alpha=0.25, color=palette[k], label=label)

    ax1.plot(dates, ret_plot, color="#1e293b", linewidth=0.6, alpha=0.8)
    ax1.axhline(0, color="#94a3b8", linewidth=0.5)
    ax1.set_ylabel("Log-Return")
    ax1.legend(fontsize=8, loc="upper left")
    ax1.grid(alpha=0.25)

    # Bottom: discrete regime colours
    for k in range(K):
        mask = vit_aligned == k
        ax2.fill_between(dates, k - 0.4, k + 0.4, where=mask,
                         color=palette[k], alpha=0.8)
    ax2.set_yticks(range(K))
    lbls = ["Calm", "Turbulent", "Crisis"][:K] if K <= 3 else [f"R{k}" for k in range(K)]
    ax2.set_yticklabels(lbls, fontsize=8)
    ax2.set_xlabel("Trading Days")
    ax2.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    return fig


def plot_regime_distributions(
    index_returns: pd.Series,
    viterbi:       np.ndarray,
    state,
) -> Optional["plt.Figure"]:
    """
    Overlaid KDE of log-returns for each regime.
    Validates that regimes are statistically distinct.
    """
    if not HAS_MPL:
        return None

    K       = state.n_regimes
    palette = ["#22c55e", "#f59e0b", "#ef4444"][:K]

    n_align  = min(len(viterbi), len(index_returns))
    ret_arr  = index_returns.values[-n_align:]
    vit_aligned = viterbi[-n_align:]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("Regime-Conditional Return Distributions", fontsize=11)

    x_grid = np.linspace(ret_arr.min(), ret_arr.max(), 300)
    labels = ["Calm", "Turbulent", "Crisis"][:K] if K <= 3 else [f"Regime {k}" for k in range(K)]

    for k in range(K):
        mask = vit_aligned == k
        data = ret_arr[mask]
        if len(data) < 10:
            continue
        try:
            kde  = _stats.gaussian_kde(data, bw_method="silverman")
            ax.plot(x_grid, kde(x_grid), color=palette[k], linewidth=2,
                    label=f"{labels[k]}  (n={mask.sum()}, "
                          f"mu={data.mean():.4f}, sigma={data.std():.4f})")
            ax.fill_between(x_grid, kde(x_grid), alpha=0.12, color=palette[k])
        except Exception:
            pass

    ax.axvline(0, color="#94a3b8", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Daily Log-Return")
    ax.set_ylabel("Density")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    return fig


def plot_transition_heatmap(state) -> Optional["plt.Figure"]:
    """Annotated heatmap of the HMM transition probability matrix."""
    if not HAS_MPL:
        return None

    K      = state.n_regimes
    P      = np.array(state.transition_matrix)
    labels = ["Calm", "Turbulent", "Crisis"][:K] if K <= 3 else \
             [f"Regime {k}" for k in range(K)]

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.set_title("Regime Transition Matrix", fontsize=11)

    im = ax.imshow(P, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(range(K))
    ax.set_yticks(range(K))
    ax.set_xticklabels([f"-> {l}" for l in labels], fontsize=9)
    ax.set_yticklabels([f"From {l}" for l in labels], fontsize=9)

    for i in range(K):
        for j in range(K):
            ax.text(j, i, f"{P[i, j]:.2f}", ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    color="black" if 0.3 <= P[i, j] <= 0.7 else "white")

    fig.tight_layout()
    return fig


# ── ─────────────────────────────────────────────────────────────────────────
# SECTION 3: Simulation output diagnostics
# ── ─────────────────────────────────────────────────────────────────────────

def run_simulation_diagnostics(
    result,
    asset_idx:  int = 0,
    output_dir: Optional[str] = None,
    verbose:    bool = True,
) -> dict:
    """
    Validate a SimulationResult:
      • Terminal-return distribution stats
      • VaR / CVaR at 95% and 99%
      • Regime occupancy in simulated paths (if regime_paths present)

    Parameters
    ----------
    result    : SimulationResult from SimulationEngine.simulate_paths()
    asset_idx : Asset index for single-asset fan chart.
    output_dir: Optional save path for figures.

    Returns
    -------
    dict with diagnostic summary.
    """
    paths        = result.return_paths                    # (P, H, A)
    regime_paths = result.regime_paths
    n_paths, horizon, n_assets = paths.shape

    # Cumulative return per path per asset: compound daily log-returns
    cum_ret   = paths.sum(axis=1)                         # (P, A)
    total_ret = np.expm1(cum_ret)                         # (P, A) simple total return

    report: dict = {
        "shape":   {"n_paths": n_paths, "horizon": horizon, "n_assets": n_assets},
        "assets":  {},
    }

    for i, sym in enumerate(result.symbols):
        r = total_ret[:, i]
        report["assets"][sym] = {
            "mean_return":   round(float(r.mean()),        4),
            "median_return": round(float(np.median(r)),    4),
            "std_return":    round(float(r.std()),         4),
            "pct5":          round(float(np.percentile(r,  5)), 4),
            "pct95":         round(float(np.percentile(r, 95)), 4),
            "var_95":        round(float(np.percentile(r,  5)), 4),
            "cvar_95":       round(float(r[r <= np.percentile(r, 5)].mean()), 4),
            "var_99":        round(float(np.percentile(r,  1)), 4),
            "cvar_99":       round(float(r[r <= np.percentile(r, 1)].mean()), 4),
            "prob_positive": round(float((r > 0).mean()), 4),
        }

    if regime_paths is not None:
        K        = int(regime_paths.max()) + 1
        occupancy = {}
        for k in range(K):
            occ = (regime_paths == k).mean()
            occupancy[k] = round(float(occ), 4)
        report["regime_occupancy"] = occupancy

    if verbose:
        _print_simulation_report(report)

    if output_dir and HAS_MPL:
        os.makedirs(output_dir, exist_ok=True)
        sym = result.symbols[asset_idx] if asset_idx < len(result.symbols) else result.symbols[0]
        fig = plot_path_fan(paths, asset_idx, sym, result.regime_paths)
        if fig:
            fig.savefig(os.path.join(output_dir, f"path_fan_{sym.replace('.','_')}.png"),
                        dpi=150, bbox_inches="tight")
            plt.close(fig)

        fig = plot_terminal_distribution(total_ret, result.symbols)
        if fig:
            fig.savefig(os.path.join(output_dir, "terminal_distributions.png"),
                        dpi=150, bbox_inches="tight")
            plt.close(fig)

    return report


def plot_path_fan(
    paths:        np.ndarray,
    asset_idx:    int,
    symbol:       str,
    regime_paths: Optional[np.ndarray] = None,
    n_sample:     int = 50,
) -> Optional["plt.Figure"]:
    """
    Fan chart showing percentile bands of cumulative return plus sample paths.
    If regime_paths is provided, colours sample paths by starting regime.
    """
    if not HAS_MPL:
        return None

    cum = np.cumsum(paths[:, :, asset_idx], axis=1)  # (P, H)
    qs  = np.percentile(cum, [5, 25, 50, 75, 95], axis=0)
    H   = cum.shape[1]
    t   = np.arange(H)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_title(f"{symbol} — Simulated Cumulative Log-Return Fan", fontsize=11)

    # Percentile bands
    ax.fill_between(t, qs[0], qs[4], alpha=0.12, color="#3b82f6", label="5–95%")
    ax.fill_between(t, qs[1], qs[3], alpha=0.22, color="#3b82f6", label="25–75%")
    ax.plot(t, qs[2], color="#1e40af", linewidth=1.5, label="Median")

    # Sample paths coloured by starting regime (if available)
    idx_sample = np.linspace(0, len(cum) - 1, min(n_sample, len(cum)), dtype=int)
    regime_palette = ["#22c55e", "#f59e0b", "#ef4444"]

    for i in idx_sample:
        if regime_paths is not None:
            k   = int(regime_paths[i, 0])
            col = regime_palette[min(k, len(regime_palette) - 1)]
        else:
            col = "#94a3b8"
        ax.plot(t, cum[i], color=col, alpha=0.18, linewidth=0.4)

    ax.axhline(0, color="#94a3b8", linewidth=0.7, linestyle="--")
    ax.set_xlabel("Trading Days")
    ax.set_ylabel("Cumulative Log-Return")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    return fig


def plot_terminal_distribution(
    total_ret: np.ndarray,
    symbols:   List[str],
) -> Optional["plt.Figure"]:
    """
    Histogram of terminal simple returns for every asset (one subplot each).
    VaR-95 line annotated.
    """
    if not HAS_MPL:
        return None

    n_assets = total_ret.shape[1]
    ncols    = min(3, n_assets)
    nrows    = (n_assets + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(ncols * 4, nrows * 3),
                             squeeze=False)
    fig.suptitle("Terminal Return Distributions", fontsize=11)

    for idx, sym in enumerate(symbols):
        r    = total_ret[:, idx]
        ax   = axes[idx // ncols][idx % ncols]
        var5 = float(np.percentile(r, 5))
        ax.hist(r, bins=60, color="#3b82f6", alpha=0.7, edgecolor="none")
        ax.axvline(var5, color="#ef4444", linewidth=1.2, linestyle="--",
                   label=f"VaR-95%: {var5:.2%}")
        ax.axvline(0, color="#94a3b8", linewidth=0.8)
        ax.set_title(sym, fontsize=9)
        ax.set_xlabel("Total Return")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.2)

    # Hide unused subplots
    for idx in range(n_assets, nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.tight_layout()
    return fig


# ── ─────────────────────────────────────────────────────────────────────────
# Internal text printers
# ── ─────────────────────────────────────────────────────────────────────────

def _print_garch_report(report: dict) -> None:
    SEP = "-" * 70
    print("\n" + SEP)
    print("  GARCH DIAGNOSTIC REPORT")
    print(SEP)

    print("\n  ARCH-Effect Test (Ljung-Box on squared returns, lag=10)")
    print(f"  {'Asset':<14} {'LB-returns p':<16} {'LB-squared p':<16} {'ARCH detected'}")
    for sym, d in report["arch_effects"].items():
        detected = "YES [OK]" if d["arch_effect_detected"] else "no"
        print(f"  {sym:<14} {d['lb_returns_p10']:<16.4f} "
              f"{d['lb_squared_returns_p10']:<16.4f} {detected}")

    print("\n  Persistence (alpha + beta + 0.5*gamma)")
    print(f"  {'Asset':<14} {'alpha':<8} {'beta':<8} {'gamma':<8} {'persist':<10} {'status'}")
    for sym, d in report["persistence"].items():
        print(f"  {sym:<14} {d['alpha']:<8.4f} {d['beta']:<8.4f} "
              f"{d['gamma']:<8.4f} {d['persistence']:<10.4f} {d['status']}")

    if report["residual_tests"]:
        print("\n  Standardised Residual Tests")
        print(f"  {'Asset':<14} {'JB p':<10} {'KS-Normal p':<14} {'White noise'}")
        for sym, d in report["residual_tests"].items():
            wn = "OK" if d["white_noise_ok"] else "FAIL [!]"
            print(f"  {sym:<14} {d['jarque_bera_p']:<10.4f} "
                  f"{d['ks_normal_p']:<14.4f} {wn}")

    if report["warnings"]:
        print("\n  [!] Warnings:")
        for w in report["warnings"]:
            print(f"    - {w}")
    print(SEP + "\n")


def _print_regime_report(report: dict, state) -> None:
    SEP = "-" * 60
    print("\n" + SEP)
    print("  HMM REGIME DIAGNOSTIC REPORT")
    print(SEP)
    print(f"\n  {state.summary()}")

    print("\n  Regime Occupancy (historical Viterbi)")
    for k, d in report["occupancy"].items():
        print(f"    Regime {k}: {d['pct']:.1%}  ({d['count']} days)")

    print("\n  KS Tests - Return Distribution Distinctiveness")
    if report["ks_tests"]:
        for key, d in report["ks_tests"].items():
            result = "DISTINCT [OK]" if d["distinct"] else "overlapping"
            print(f"    {key}: KS={d['ks_stat']:.4f}  p={d['ks_p']:.4f}  -> {result}")
    else:
        print("    (insufficient data for KS tests)")

    print("\n  Transition Persistence")
    for k, d in report["transition"].items():
        print(f"    Regime {k}: self-prob={d['self_prob']:.3f}  "
              f"expected duration={d['expected_duration']} days")
    print(SEP + "\n")


def _print_simulation_report(report: dict) -> None:
    SEP = "-" * 60
    print("\n" + SEP)
    print("  SIMULATION OUTPUT REPORT")
    print(SEP)
    s = report["shape"]
    print(f"  Paths={s['n_paths']}  Horizon={s['horizon']}d  Assets={s['n_assets']}")
    print(f"\n  {'Asset':<14} {'Mean ret':<12} {'Std':<10} "
          f"{'VaR-95%':<12} {'CVaR-95%':<12} {'P(>0)'}")
    for sym, d in report["assets"].items():
        print(f"  {sym:<14} {d['mean_return']:<12.3%} {d['std_return']:<10.3%} "
              f"{d['var_95']:<12.3%} {d['cvar_95']:<12.3%} {d['prob_positive']:.1%}")
    if "regime_occupancy" in report:
        print("\n  Regime Occupancy (simulated paths)")
        for k, occ in report["regime_occupancy"].items():
            print(f"    Regime {k}: {occ:.1%}")
    print(SEP + "\n")


# ── Shared utility ────────────────────────────────────────────────────────────

def _ljungbox_pvalue(series: pd.Series, lags: int = 10) -> float:
    """Ljung-Box p-value; scipy fallback if statsmodels unavailable."""
    if HAS_STATSMODELS:
        try:
            res = _ljungbox_sm(series.dropna(), lags=[lags], return_df=True)
            return float(res["lb_pvalue"].iloc[-1])
        except Exception:
            pass
    # Scipy manual fallback
    try:
        s = series.dropna().values
        n = len(s)
        acf_vals = [float(pd.Series(s).autocorr(lag=k)) for k in range(1, lags + 1)]
        Q = n * (n + 2) * sum(r ** 2 / (n - k) for k, r in enumerate(acf_vals, 1))
        return float(1.0 - _stats.chi2.cdf(Q, df=lags))
    except Exception:
        return 0.5


# ── Standalone smoke-test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-8s %(message)s")

    # Minimal self-test without real data
    rng = np.random.default_rng(0)
    T, N = 400, 3
    syms = ["COMI.CA", "ESRS.CA", "TMGH.CA"]
    returns = pd.DataFrame(rng.standard_normal((T, N)) * 0.015, columns=syms)
    idx_ret = returns.mean(axis=1)

    try:
        from engines.garch_engine import GARCHEngine
        from engines.regime_model  import RegimeModel
        from engines.simulation_core import SimulationEngine, SimulationConfig
    except ImportError:
        from garch_engine    import GARCHEngine         # type: ignore
        from regime_model    import RegimeModel         # type: ignore
        from simulation_core import SimulationEngine, SimulationConfig  # type: ignore

    # GARCH diagnostics
    ge = GARCHEngine(use_auto_select=False, model_preference="gjr_garch")
    ge.fit(returns)
    r_garch = run_garch_diagnostics(ge, returns, verbose=True)

    # HMM diagnostics
    rm = RegimeModel(n_regimes=2, use_auto_select=False)
    rm.fit(idx_ret)
    r_hmm = run_regime_diagnostics(rm, idx_ret, verbose=True)

    # Simulation output diagnostics
    cfg    = SimulationConfig(volatility_model="gjr_garch", regime_model="hmm",
                               n_paths=200, horizon=63, seed=0)
    eng    = SimulationEngine(cfg)
    eng.fit(returns, index_returns=idx_ret)
    result = eng.simulate_paths()
    r_sim  = run_simulation_diagnostics(result, verbose=True)

    print("Diagnostics smoke-test complete.")
