# MATH-004: Investment Risk Evaluation

**Status:** Draft v1.0  
**Version:** 1.0  
**Author:** Gemini (Architect & Validator)  
**Classification:** Mathematical Specification — Normative  
**Depends On:**
- RFC-000 to RFC-005
- MATH-001, MATH-002, MATH-003

---

## 1. Purpose

Defines how to compute overall **investment risk** for an opportunity by combining profitability, liquidity, and competition signals.

Primary consumer: `RiskEngine`

---

## 2. Value Objects

### Risk

```math
\text{Risk} ::= (
  overall\_risk\_score: \mathbb{R} \in [0, 100],
  components: Map<String, \mathbb{R}>,
  risk\_level: Low | Medium | High | Critical
)
```

---

## 3. Mathematical Model

### 3.1 RiskInput

```math
\text{RiskInput} ::= (
  roi: ROI,
  liquidity: Liquidity,
  competition: Competition,
  capital\_required: Money,
  user\_risk\_tolerance: \mathbb{R}
)
```

### 3.2 Risk Calculation (Weighted Composition)

```math
\text{ProfitabilityRisk} = \max(0, 50 - \text{roi.roi\_percent})
```

```math
\text{LiquidityRisk} = 100 - \text{liquidity.liquidity\_score}
```

```math
\text{CompetitionRisk} = \text{competition.competition\_score}
```

```math
\text{OverallRisk} = 
(\text{ProfitabilityRisk} \times 0.35) + 
(\text{LiquidityRisk} \times 0.40) + 
(\text{CompetitionRisk} \times 0.25)
```

Risk is clamped to [0, 100].

---

## 4. Determinism

Fully deterministic composition of previous analytical results.

---

**End of MATH-004**