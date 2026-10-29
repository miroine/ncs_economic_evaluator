# NCS Economics Workbench — v4

Streamlit prototype for offshore/NCS project economics and decision analysis.

## v4 additions

- Bidirectional Streamlit decision-tree component (browser JavaScript ↔ Python state).
- Drag/drop decision, chance and outcome nodes with editable chance probabilities.
- Outcome nodes link directly to named economic scenarios and display live scenario NPV.
- Tree edits are evaluated immediately by the Python EMV rollback engine.
- Decision-tree Monte Carlo: correlated uncertain project economics propagate through scenario NPVs and tree rollback.
- Uncertainty distributions: lognormal, normal and triangular.
- Gaussian-copula correlation controls for oil/gas, CAPEX/OPEX and production/CAPEX.
- Correlation diagnostics and reproducible random seeds.
- Added v4 tests for correlation and stochastic tree evaluation.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important fiscal-model status

The current tax calculation remains an intentionally simplified placeholder. It is **not decision-grade NCS petroleum tax modelling**. The architecture keeps fiscal calculations replaceable so a validated tax-vintage engine can be introduced without changing scenario, uncertainty, or decision-tree interfaces.

## Suggested next build

1. Fiscal-vintage NCS tax engine with explicit tax bases, loss handling, depreciation/investment treatment, timing and audit trail.
2. Tree branch-specific actions/costs and information-acquisition costs.
3. Perfect/partial information analysis (EVPI/EVSI).
4. Schedule uncertainty and correlated production profiles rather than one scalar production multiplier.
5. Project save/load format and Excel import/export templates.

## v5 additions
- Auditable post-2022 NCS cash-flow special-tax baseline (22% ordinary / 71.8% technical special rate), with six-year ordinary depreciation and explicit audit limitations.
- Project JSON save/load schema.
- EVPI calculation primitive for value-of-information workflows.
- Fiscal logic isolated in `economics/fiscal_ncs.py` for future vintage/transitional-rule expansion.

**Fiscal warning:** the included NCS module is an analytical project-level baseline, not tax advice or a substitute for company tax models. It intentionally excludes financing allocation, norm-price adjustments, company portfolio offsets and temporary-rule uplift/vintage details.

## v6 — analysis plots, breakeven, units and real/nominal conventions

Version 6 adds a common economics-convention layer and a richer analysis workspace:

- Tornado chart covering oil price, gas price, production, CAPEX and OPEX.
- Sensitivity curves with configurable driver selection.
- Oil-price breakeven solver and NPV-vs-oil-price breakeven plot.
- Annual pre-/after-tax cash flow and cumulative cash-flow / cumulative-NPV plots.
- Project value waterfall/bridge for oil revenue, gas revenue, CAPEX, OPEX, decommissioning and tax.
- Display conversion for NOK/kNOK/MNOK/BNOK, bbl/kbbl/MMbbl/MSm3 oil, and Sm3/kSm3/MSm3/BCM/MMboe gas.
- Explicit real vs nominal money basis, base year, inflation/escalation inputs, and real/nominal discount-rate conversion using the Fisher relationship.
- Canonical internal calculation units remain MNOK, MMbbl and MSm3 to prevent display-unit changes from changing project economics.

### Convention rule

Use a real discount rate with real/constant-money cash flows, or a nominal discount rate with nominal/money-of-the-day cash flows. If the entered discount-rate basis differs from the selected cash-flow basis, the app converts it using the configured general inflation rate and exposes the effective rate in the dashboard/audit output.

### Profile editing and economics metrics

The **Production & costs** module supports manual edits with an explicit **Apply manual profile** action, plus CSV and Excel profile imports. The downloadable CSV template uses canonical units and columns: `year`, `oil_mmbbl`, `gas_msm3`, `capex_mnok`, `opex_mnok`, and optional `decom_mnok`. The **Economics** table converts oil and gas volumes into the selected display units. The dashboard reports pre-tax and after-tax NPV, oil-price/deck breakeven, and minimum economic volume (MEV) in MMboe.

The NCS fiscal engine remains an analytical project-level model. Company tax position, financing allocation, norm-price effects and all transitional/vintage rules must be reconciled before decision-grade use.

## Performance, display units and consulting-inspired design

- **McKinsey-inspired** is the default theme: white canvas, navy typography, blue
  accents and restrained chart/card styling. This is an independent visual
  interpretation, not an official McKinsey theme or endorsement. The existing
  North Sea, Midnight Offshore and Arctic Light themes remain selectable.
- Monte Carlo, tornado, sensitivity curves and spider plots use batched NumPy
  calculations, with the same shared fiscal ledger as the full cash-flow model.
  NPV-only analysis and breakeven searches no longer solve IRR unnecessarily.
- Sensitivity, breakeven and market-deck views execute only when selected.
  Canonical analysis results are cached against their model inputs; changing
  display units does not recalculate project economics.
- Monte Carlo now respects the active annual market deck and economic cutoff.
  Changed model or uncertainty inputs require a new run instead of displaying
  stale results as current. Outdated model samples are excluded from workbook
  exports. P10/P90 use non-exceedance notation: low/high NPV, respectively.
- Tables, monetary chart legends/axes, scenarios, concepts, snapshots and Monte
  Carlo results convert values **and labels** together. Decision-tree live NPVs
  and fallback inputs also follow the selected money unit; stored tree values
  remain canonical MNOK. Changing profile-editor units resets its edit buffer,
  so apply pending edits before switching units.
- The displayed cash-flow CSV uses selected units in its column headings.
  Audit CSVs, Excel workbooks, project JSON and profile import templates retain
  canonical MNOK / MMbbl / MSm3 units for reproducibility. Price, cutoff,
  generator and exploration input fields retain their explicitly labelled
  canonical units; MEV remains a combined hydrocarbon volume in MMboe.

### Measured performance

Local comparison against the previous engine, using the default 15-year annual
profile, NCS fiscal V2, flat prices and the same random seed:

| Calculation | Previous | Updated |
|---|---:|---:|
| Monte Carlo, 2,000 iterations | 68.33 s | 0.018 s |
| Spider sensitivity, 54 cases | 1.58 s | 0.016 s |
| Six-variable breakeven table | 8.15 s | 3.04 s |

These are engine timings on one machine, excluding UI rendering and cache hits,
not universal latency guarantees. Monte Carlo and spider NPV differences were
below 1e-8 MNOK; breakeven factors agreed within 1e-8. Fiscal/cutoff regression
tests cover annual, quarterly and monthly profiles and all supported tax modes.

Run the regression and Streamlit workflow tests with:

```bash
python -m pytest -q
```

## Version 7 — visual design system

The original design layer includes **North Sea**, **Midnight Offshore**, and **Arctic Light**, alongside the newer **McKinsey-inspired** default. The selected theme is applied to the Streamlit workspace, Plotly figures and decision-tree component.

### Attribution and intended use

**Made by Merouane Hamdani. For educational purposes only — non-commercial.**

The application is an educational analytical workbench. It is not investment, tax, legal, reserves, accounting, or engineering advice. Fiscal and economic outputs must be independently validated before use in real project decisions. The non-commercial statement is an intended-use notice and is not, by itself, a complete software license.

## Version 8 additions
- Editable annual oil-price, gas-price and USD/NOK market decks
- Deck-aware project cash-flow calculation with interpolation for missing years
- Spider sensitivity across oil, gas, production, CAPEX, OPEX and FX
- Multi-variable breakeven factors; market-deck oil breakeven is reported as a uniform deck multiplier
- Monte Carlo NPV exceedance / S-curve
- Stacked oil/gas revenue view and pre-tax-to-after-tax tax bridge
- Excel analysis workbook export (assumptions, profile, cash flow, market deck, scenarios, Monte Carlo and metadata)
- V7 themes, real/nominal conventions, unit conversions and decision-tree analysis retained

**Made by Merouane Hamdani — for educational purposes only, non-commercial.**

## V9 — decision-grade workflow additions

V9 adds an integrated economic-cutoff and decision-analysis layer:

- Cutoff modes: none, hard cutoff, consecutive negative operating cash flow, and look-ahead economic limit.
- Optional minimum oil/gas rate constraints and a hard boundary.
- Decommissioning can be moved automatically relative to calculated cessation.
- Generated ramp / plateau / decline production profiles constrained by recoverable oil volume.
- Development-concept comparison (e.g. tie-back / FPSO / platform) with independent CAPEX, OPEX, production and schedule transforms.
- Expanded cutoff-aware breakevens for oil, gas, production/resources, CAPEX, OPEX and FX.
- EVPI and EVSI analysis with signal accuracy, information cost, and net value of information.
- Cutoff audit output exposing mode, cessation period and trigger reason.

### Cutoff convention
Economic cutoff is tested on operating economics (revenue less OPEX), rather than total project cash flow, so development CAPEX and decommissioning do not themselves trigger field cessation. The look-ahead rule allows a temporary negative period to continue when the configured future operating window recovers positive incremental value. This is an educational analytical implementation; users should configure the rule to match their organization's economic-limit convention.

## V10 additions

V10 upgrades the workbench into a more integrated development-economics workflow:

- annual, quarterly and monthly cash-flow resolution with fractional-year discounting and CAPEX phasing;
- named Low/Base/High oil, gas and FX decks;
- cutoff-aware breakevens including price, production/resources, CAPEX, OPEX, FX, schedule and discount-rate diagnostics;
- development concept comparison retained separately from uncertainty scenarios;
- decision-tree branch costs and delays plus EVPI/EVSI tools;
- Monte Carlo downside and input/NPV correlation diagnostics;
- reserves-driven ramp/plateau/decline production using STOIIP, recovery factor, uptime and facility capacity;
- NCS fiscal V2 analytical engine with ordinary loss carry-forward, depreciation and transparent tax bases;
- configurable Analysis Studio for metric-vs-variable curves;
- V10 project schema, version snapshots and downloadable investment-decision summary.

The economic cutoff remains a first-class rule throughout. Hard cutoff, consecutive negative operating cash flow, look-ahead economic limit, minimum production thresholds and decommissioning movement can change field life dynamically during sensitivities and breakeven calculations.

**Made by Merouane Hamdani — for educational purposes only, non-commercial.** This application is an analytical learning tool, not investment, tax, legal, reserves, accounting or engineering advice.

## V11 — Exploration + Development Decision System

V11 extends V10 with:
- prospect risking using geological chance of success, dry-hole cost and conditional discovery-size/value cases;
- exploration EMV distributions that can feed appraisal and development decisions;
- facilities/commercial transformations for tariffs, transport, host capacity, third-party income and time-varying working interest;
- category-based cost phasing with independent timing and escalation;
- stage-based schedule-risk Monte Carlo across approvals, drilling, construction and commissioning;
- explicit Discovery → Appraisal → Concept Select → FEED → FID → Execute → Operate decision gates;
- constrained portfolio selection under annual CAPEX and project-count limits;
- model-assurance checks for reserves balance, market-deck coverage, probabilities, cessation/decommissioning timing and real/nominal consistency;
- a V11 exploration & portfolio workspace integrating these analyses with the existing cutoff-aware project economics.

The portfolio optimizer is intentionally an exact small-set educational optimizer; large corporate portfolios should use a dedicated mathematical-programming solver. Fiscal, reserves and commercial outputs remain educational analytical estimates requiring independent validation.

**Made by Merouane Hamdani — for educational purposes only, non-commercial.**


## V12.1 audited maintenance release

- Explicit annual-total vs per-period semantics for subannual profiles to prevent accidental x4/x12 fixed-cost multiplication.
- Explicit `gross_field` vs `net_company` commercial bases for tariffs, transport, third-party income and incoming cash flow.
- Annual-basis Fiscal V2 ledger for monthly/quarterly models, with annual tax allocated back to the final model period of each year.
- Added dimensional, round-trip, revenue-identity, Mboe-capacity, ownership and annual/subannual reconciliation tests.
- Fiscal V2 remains an educational project-level approximation, not a statutory/company tax calculation.


## V12 integrated field development
V12 adds resource/reserves balance, well deliverability and facility constraints, development schedule simulation, category/multi-currency costs, physical emissions and carbon economics, a unified uncertainty register, project-linked decision terminal states, a calculation inspector, and a structural model-validation gate. Manual forecast mode remains supported.


## V12.1 audit fixes
- Daily well/facility rates use actual calendar days per annual/quarterly/monthly period.
- Development schedule durations/delays have explicit calendar-month semantics (legacy V12 decimal-year schedules remain readable).
- Project-linked terminal-state delays accept `delay_months`; legacy `delay_years` maps to months. Economic flows are shifted by the calendar-equivalent number of model periods, so delay affects NPV rather than only year labels.
- Cross-resolution regression tests cover leap-year/month lengths, volume conservation, schedule timing and decision-delay behavior.

## V12.2 audit-fix release

V12.2 is a user-facing reliability repair following a full V12.1 application audit.

- Replaced the 14 eager Streamlit tabs with single-module navigation. Only the selected workspace executes, preventing hidden Monte Carlo, breakeven, schedule, uncertainty and export workloads from rerunning on every click.
- Monte Carlo and V12 schedule/register simulations are explicit-run and their results persist in session state while navigating.
- Project JSON loading now has a real Apply action and restores profile, market deck, scenarios, decision tree, concepts, snapshots, core assumptions, resolution and CAPEX phasing.
- V12 wells, schedule, FX deck, cost lines, uncertainty register and project-linked terminal states are editable instead of hard-coded demonstrations.
- Integrated physical production can be applied back to the project economics profile.
- Decision-tree workspace now supports a scrollable canvas, zoom controls, Ctrl-wheel zoom, responsive toolbar and connector-dot drag connections.
- Responsive CSS allows metric/input columns to wrap on narrower screens and keeps data editors horizontally scrollable.
- Added UI-architecture regression tests in addition to the economics suite.

### Verification note
The release passes the Python compile check and automated test suite. The packaging environment used for this audit did not contain Streamlit and could not download packages, so a live browser launch was not available during packaging. Run `pip install -r requirements.txt` and `streamlit run app.py` in the deployment environment for the final browser/device acceptance test.
