# US equities market-wide alpha research — Databricks notebook bundle

Three importable Databricks Python notebooks that prototype **cross-sectional alpha ranking**, **triple-barrier meta-labeling**, and a **Gaussian-mixture market regime router**. They create Delta tables and track the models using MLflow. A **demo feed is built in**, so the complete workflow can be exercised without real market data.

> **This is a research / paper-trading prototype, not a validated profitable investment strategy.** It never places orders. Its simulated labels, barrier results, and top-ranked diagnostics do not substitute for a fill-aware, transaction-cost-aware backtest.

## Notebook order

| Notebook | Role | Main tables |
| --- | --- | --- |
| `01_ingest_and_features.ipynb` | Read 5-minute bars, validate OHLCV, compute rolling and cross-sectional features | `equity_bronze`, `equity_silver_5m`, `equity_features_5m` |
| `02_train_ranker_meta_regime.ipynb` | Calculate future labels on full bar history; fit LightGBM LambdaRank, RandomForest barrier meta classifier and GMM regime; inspect chronological holdout and walk-forward folds | `alpha_model_registry` + MLflow models |
| `03_live_rank_and_paper_signals.ipynb` | Score latest complete 5-minute bar; rank securities; apply meta-model + volatility-regime controls; persist versioned research signals | `alpha_paper_signals` |

## Quick start (built-in demo)

1. Use a Databricks **ML runtime** with Spark/Delta, MLflow, and permission to create tables in the selected Unity Catalog catalog/schema. Notebook 02 installs `lightgbm==4.6.0` with `%pip`.
2. Import all three `.ipynb` files into Databricks Workspace (Import → Files or equivalent).
3. Run Notebook 01 with `data_mode=demo`, `write_mode=bootstrap`, `catalog=main`, `schema=stock_alpha`. Change `main` if you don't have a writable catalog. It produces ~172k synthetic market bars (48 names × 46 sessions × 78 five-minute bars), before eligibility filtering.
4. Run Notebook 02 with the same catalog and schema; set a usable `experiment_path` (default `/Shared/us_equity_alpha`). It writes three MLflow model references to the registry (or two if meta validation lacks both classes).
5. Run Notebook 03 with `run_mode=demo`. Inspect the ranked stocks and `PAPER_BUY_CANDIDATE` / `WATCH_ONLY` signals in `alpha_paper_signals`.

All widgets are near the start of each notebook. Demo rows are **artificial**, and demo scoring shows a historical timestamp rather than pretending it is live.

## Connect your live feed

Notebook 01 expects a **Delta table containing fully closed, time-synchronized five-minute bars**, not raw unordered trades. Define and populate a source with:

```sql
-- Run after creating main.market_data, or substitute your catalog/schema.
CREATE TABLE IF NOT EXISTS main.market_data.us_equity_5m (
  event_time TIMESTAMP, -- end of the completed 5-minute bar in UTC
  symbol STRING,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  volume DOUBLE,
  sector STRING,
  bid DOUBLE,            -- optional synchronized Level-1 quote
  ask DOUBLE,
  bid_size DOUBLE,
  ask_size DOUBLE
) USING DELTA;
```

Set Notebook 01's `data_mode=table` and `source_table=<your_3_part_table>`. To initially backfill features, choose `write_mode=bootstrap`; for subsequent updates, choose `write_mode=incremental` with at least 20 **prior trading days** available inside `lookback_days` (default 55 calendar days). `refresh_days` controls the most recent days that are merged; delayed upstream corrections earlier than that need a dedicated backfill/reconciliation job.

**Run a Databricks Workflow:** `ingest / bar-complete event → 01 (incremental) → 03 (live)`. Run Notebook 02 separately on your retraining schedule (e.g. weekly, after validation) and review model performance before promotion. The user-defined bar-completeness signal is necessary to know the full market cross-section has arrived before 03 is triggered. A maximum timestamp and minimum count alone do not prove completeness.

Databricks recommends trigger `availableNow=True` for bounded streaming increments, with the proper checkpoint, when using Structured Streaming. The upstream aggregation of ticks into bars is deliberately not included here: correct chronological OHLC aggregation requires ordering and careful treatment of late trades. See [Databricks streaming triggers](https://docs.databricks.com/aws/en/structured-streaming/triggers).

### Data semantics and assumptions

- `event_time` refers to **bar end** and is stored as a UTC timestamp. Notebook 01 converts to `America/New_York` to recognize the 09:35–16:00 ET regular-hours 5-minute closes (including DST). Real early-close days and holidays require an exchange calendar upstream.
- Input rows must have **unique `(symbol, event_time)`** identifiers and internally consistent OHLCV. Duplicate/conflicting bars produce a hard failure, rather than a silently arbitrary `first()` record.
- The sample filters symbols when current close is at least **$5**, prior-day ADV20 is at least **500,000 shares**, and there are at least 15 preceding trading sessions. Change these controls to your risk appetite and assets.
- Prices **and volumes** should be consistently adjusted for splits when building historic models, and historical symbol mappings, corporate actions, sector membership, suspended/delisted symbols, and universe membership should be point-in-time correct.
- Market benchmark in training is the **same-timestamp equal-weight average forward return** among Silver symbols. It is **not SPY total return**. Replace it with a separately timestamp-aligned SPY/sector-adjusted benchmark if appropriate.
- `book_imbalance` is only a bar-end Level-1 size imbalance if supplied. It is **not true order-flow imbalance** or a deep Level-2 Transformer, which requires event-sequenced quotes/trades.
- Features are computed as of the **completed** bar; entry is modeled at the **following bar's open** and labels end within the same NY session. The label builder also verifies exact five-minute continuity for forward horizons.
- Current prototype does **not** explicitly enforce Databricks Feature Store time-series keys; the features and labels are joined by exact `(symbol,event_time)` and generated separately. For joining nonaligned external fundamental/news features, use point-in-time `FeatureLookup` with `timeseries_columns` per [Databricks guidance](https://docs.databricks.com/aws/en/machine-learning/feature-store/time-series).

## Models and outputs

**Ranking (LightGBM LambdaRank).** Each bar end defines a query/group of eligible stocks. Target is the quintile of future **market excess** returns over `rank_horizon_bars` (default 6 = 30 minutes) based on next-open entry and later close. Features include momentum, 12-bar volatility, RSI, historical same-time-of-day relative volume, CLV, liquidity, residual momentum, current market context, and within-sector percentile ranks. Train/validation/test are chronological with a one-session embargo and two expanding walk-forward diagnostics.

**Triple-barrier meta (RandomForest).** Conditional on ranker candidates, binary target=1 means a future high crosses **profit +0.6%** before a future low crosses **stop –0.4%** within 12 five-minute bars; simultaneous high/low crosses count as stop. Validation-only ranker candidate predictions train the meta-model; **test rows are not used to fit either model**. The classifier's probability is **not automatically calibrated**; thresholds are experimental.

**Regime router (GMM).** Unsupervised 3-component mixture model of live bar's market return, 12-bar volatility and 12-bar momentum. Cluster labels are ordered by in-sample mean realized volatility (`LOW_VOL`, `MID_VOL`, `HIGH_VOL`). Prototype signal risk multiplier is 1, 0.5, or 0 respectively; it is not a statistically optimized rule.

**Signals.** Notebook 03 emits rankings and, only when meta-model and threshold pass and regime allows, `PAPER_BUY_CANDIDATE`. Weight is limited by widget `per_name_cap` (default 1% notional) and `portfolio_cap` (default 5%) with medium-volatility reduction. No broker integration, transaction placement, fill or return calculation exists.

## What to improve before live capital

1. Enforce **survivorship-free** historical universe, adjusted corporate actions, consolidated market calendar, symbol changes, data feed sequence/watermarks and complete bar delivery.
2. Add a realistic **order/execution simulator**: next-open availability, quotes/spread, fees, slippage, queue depth, price gaps, partial fills, short-sale/borrow where relevant, portfolio turnover and capital capacity. This implementation only reports a top-10%-signal diagnostic after a flat hypothetical cost.
3. Use repeated **purged rolling retrains**, multiple market regimes, truly held-out months/years, bootstrapped confidence bands, sector/market-neutral comparison, and probability calibration for meta-labels.
4. Scale ranking training: Notebook 02 converts selected **whole cross-sections** (capped at 450,000 rows by default) to pandas on the driver. For millions of groups, use distributed LightGBM / Ray or scale driver memory, and enforce a query-based sampling policy.
5. Add strong operational safeguards: explicit bar completeness, incremental recompute backfills, drift alerts, freshness SLAs, model registry approval, monitoring, risk limits, audit logs, data license checks and relevant compliance review.

## Source references for current APIs

- [Databricks point-in-time feature joins](https://docs.databricks.com/aws/en/machine-learning/feature-store/time-series)
- [Databricks Structured Streaming triggers](https://docs.databricks.com/aws/en/structured-streaming/triggers)
- [MLflow 3 migration: use returned model URI](https://mlflow.org/docs/latest/ml/mlflow-3/)
- [LightGBM Python ranking API](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMRanker.html)

**Environment limitation:** Notebooks were validated as notebook JSON with valid Python syntax, but **were not executed against a live Databricks cluster or your data**. Run demo first and adjust package versions, permissions, and source schema for your workspace.
