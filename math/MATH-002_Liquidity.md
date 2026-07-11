# MATH-002: Liquidity Evaluation (v1.4)

**Status:** Draft v1.4
**Version:** 1.4

## Purpose
Provides pure liquidity metrics only.

## Value Objects
Liquidity = (daily_volume, liquidity_score, depth_score)

## Equations

```
VolumeScore = min((daily_volume / V_REF) * 100, 100)
DepthScore  = min((total_sell_volume_remain / D_REF) * 100, 100)
LiquidityScore = sqrt(VolumeScore * DepthScore)
```

Note: Exit Time calculation has been removed. It now lives exclusively in MATH-005.

## Changelog

### v1.3 -> v1.4 (fix "ghost order book")
Previous equation: `LiquidityScore = (VolumeScore * 0.60) + (DepthScore * 0.40)`.

A weighted arithmetic mean lets either term carry the score even when the
other is zero. In practice this meant an item with **zero** real daily
volume (`daily_volume = 0`, e.g. because `market_history` was never
imported, or because the item genuinely never trades) could still score
up to 40/100 on liquidity purely from stale `volume_remain` sitting in
the order book. That is, by definition, a ghost order book: quantity is
offered, but nobody is moving it.

This was not an edge case. While `market_history` is empty (the state
the project starts in until the history importer is run), `VolumeScore`
is 0 for every item, so `LiquidityScore` collapsed to `DepthScore * 0.4`
across the whole dataset -- the system was effectively recommending
based on stale depth, not real liquidity.

v1.4 replaces the weighted average with a **geometric mean**. If either
component is 0, the result is 0: there is no way for "depth without
movement" to produce a positive liquidity score. It remains a pure,
one-line, deterministic formula -- no simplicity was traded away for
this fix.
