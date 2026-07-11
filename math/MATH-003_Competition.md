# MATH-003: Competition Evaluation

**Status:** Draft v1.2
**Version:** 1.2
**Author:** Gemini (Architect & Validator); v1.1/v1.2 fixes by Claude (Sprint 1 refactor)
**Classification:** Mathematical Specification — Normative
**Depends On:**
- RFC-000, RFC-002, RFC-003, RFC-005
- MATH-001, MATH-002

---

## 1. Purpose

Defines the mathematical model for measuring **structural competitive
pressure** in a market: how many rivals are active in the order book and
how dense the market is. Deliberately excludes price/spread signals,
which are the responsibility of MATH-001 (ROI) and the spread-quality
component of the opportunity score -- see changelog v1.2.

Used by:
- `CompetitionEngine`
- `RiskEngine`
- `OpportunityEngine`

---

## 2. Value Objects

### Competition

```math
\text{Competition} ::= (
  competition\_score: \mathbb{R} \in [0, 100],
  order\_pressure: \mathbb{R},
  market\_density: \mathbb{R}
)
```

---

## 3. Mathematical Model

### 3.1 Input — CompetitionInput

```math
\text{CompetitionInput} ::= (
  buy\_order\_count: \mathbb{Z},
  sell\_order\_count: \mathbb{Z},
  total\_buy\_volume: \mathbb{R},
  total\_sell\_volume: \mathbb{R}
)
```

### 3.2 Competition Score

```math
\text{OrderPressure} = \frac{\text{sell\_order\_count}}{\text{buy\_order\_count} + \text{sell\_order\_count} + 1}
```

```math
\text{MarketDensity} = \min\left( \frac{\text{total\_sell\_volume} + \text{total\_buy\_volume}}{D_{ref}} \times 100, 100 \right)
```

```math
\text{CompetitionScore} =
(\text{OrderPressure} \times 100 \times 0.60) +
(\text{MarketDensity} \times 0.40)
```

Higher score = higher structural competition (more active rivals relative
to book size).

---

## 4. Invariants & Determinism

Same as previous MATH documents. Pure and deterministic.

---

## 5. Changelog

### v1.0 -> v1.1 (fix order_pressure units)

`OrderPressure` is defined as a fraction in `[0, 1]`, but the v1.0
composition formula weighted it with `0.50` as if already on a `[0, 100]`
scale, making it contribute at most `0.5` points out of 100 -- in
practice invisible next to `MarketDensity`. v1.1 scales `OrderPressure`
to `[0, 100]` before weighting.

### v1.1 -> v1.2 (removed price_spread_percent)

v1.1 kept `price_spread_percent` as an input (weight `0.20`,
contributing positively to `CompetitionScore`) but never wired real data
into it, flagging the sign as an open question.

**Resolution:** a wide bid-ask spread does not indicate *more*
competition -- it indicates *less*. A narrow spread is the signature of
a market under real competitive pressure (many sellers undercutting each
other push the ask down; many buyers outbidding each other push the bid
up). This document's own definition confirms it: *"higher score = higher
competition (harder to sell profitably)"* -- under that definition, a
narrow spread (margin squeezed by competition) should raise the score,
and a wide spread (margin captured without contest) should lower it. The
v1.1 formula added `price_spread_percent` with a **positive** sign:
exactly inverted relative to the document's own definition.

Flipping the sign was considered and rejected: the same raw spread
already feeds the opportunity score through two other channels
(`ROIEngine`, since ROI derives from the same spread net of fees, and
the spread-quality component in `OpportunityEngine`, the same spread
gross). Adding it a third time here -- even with a corrected sign --
would make one underlying number push the final score through three
components with different roles, two rewarding a wide spread and one
penalizing it, undermining the transparency of the score breakdown.

v1.2 removes `price_spread_percent` entirely. `CompetitionScore` now
measures **only** order book structure (active rivals, market density);
price/margin remains the exclusive responsibility of MATH-001 and the
spread-quality component. The freed weight (`0.20`) is redistributed:
`OrderPressure` `0.50 -> 0.60`, `MarketDensity` `0.30 -> 0.40`.

This change has no observable effect on prior results: `price_spread_percent`
was never actually wired by any caller (`OpportunityEngine` always left
it at its default `0.0`), so this formalizes existing de facto behavior
rather than changing it.
