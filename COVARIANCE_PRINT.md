
# Covariance Diagnostics Guide

## 1. Purpose

The covariance diagnostics tool allows you to inspect and independently verify the risk-budget optimizations used in the Bottom-Up and Top-Down portfolio construction models.

It exports, for each optimization node:

- Raw covariance matrix.
- Normalized covariance matrix used by the optimizer.
- Optimized capital weights.
- Target risk contributions.
- Actual risk contributions.
- Optimization metadata.

The tool supports selecting:

- Bottom-Up or Top-Down methodology.
- A specific quarter or all available quarters.
- A specific optimization level or all levels.

The diagnostic process does not change the normal portfolio-running workflow.

---

## 2. Project Files

The following files are involved:

```text
AgawaProject/
│
├── inspect_covariance.py
├── COVARIANCE_DIAGNOSTICS.md
│
├── src/
│   ├── risk_budget.py
│   └── bottom_up/
│       └── portfolio.py
│
├── top_down/
│   └── portfolio.py
│
├── data/
│   └── daily_returns.csv
│
└── outputs/
    └── diagnostics/
```

### File responsibilities

| File | Responsibility |
|---|---|
| `risk_budget.py` | Calculates covariance matrices and optimizes risk-budget weights. |
| `src/bottom_up/portfolio.py` | Captures diagnostics for Bottom-Up optimization nodes. |
| `top_down/portfolio.py` | Captures diagnostics for Top-Down optimization nodes. |
| `inspect_covariance.py` | Selects quarters and optimization levels and exports CSV files. |
| `COVARIANCE_DIAGNOSTICS.md` | Instructions for using the diagnostics tool. |

The regular portfolio runners do not need to be modified.

---

## 3. Initial Setup

Activate your virtual environment:

```bash
source .venv/bin/activate
```

Ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

Check that all modified files compile:

```bash
python -m py_compile \
    inspect_covariance.py \
    src/risk_budget.py \
    src/bottom_up/portfolio.py \
    top_down/portfolio.py
```

---

## 4. Running the Diagnostics Tool

All commands should be executed from the project root directory.

General syntax:

```bash
python inspect_covariance.py \
    --method METHOD \
    --input INPUT_FILE \
    --return-unit UNIT \
    --quarter QUARTER \
    --level LEVEL
```

### Arguments

| Argument | Description | Options |
|---|---|---|
| `--method` | Portfolio methodology | `bottom_up`, `top_down` |
| `--input` | Input daily returns CSV | File path |
| `--return-unit` | Input return units | `decimal`, `percent` |
| `--quarter` | Quarter to inspect | `2025Q2`, `all`, etc. |
| `--level` | Optimization level | `1`–`5`, `all` |
| `--covariance-window` | Maximum historical observations | Default: `252` |
| `--min-obs` | Minimum required observations | Default: `252` |
| `--output-dir` | Export directory | Default: `outputs/diagnostics` |

**Return units:**

- `decimal`: 0.01 represents a 1% return.
- `percent`: 1.0 represents a 1% return.

Use the same units as your normal portfolio workflow.

---

## 5. Example Commands

### A. Bottom-Up: One Quarter, All Levels

```bash
python inspect_covariance.py \
    --method bottom_up \
    --input data/daily_returns.csv \
    --return-unit decimal \
    --quarter 2025Q2 \
    --level all
```

Exports all 38 optimization nodes for that quarter.

### B. Top-Down: One Quarter, All Levels

```bash
python inspect_covariance.py \
    --method top_down \
    --input data/daily_returns.csv \
    --return-unit decimal \
    --quarter 2025Q2 \
    --level all
```

Exports all 15 optimization nodes for that quarter.

### C. Bottom-Up: Only the Global Portfolio

```bash
python inspect_covariance.py \
    --method bottom_up \
    --input data/daily_returns.csv \
    --return-unit decimal \
    --quarter 2025Q2 \
    --level 5
```

### D. Top-Down: Only Level 2

```bash
python inspect_covariance.py \
    --method top_down \
    --input data/daily_returns.csv \
    --return-unit decimal \
    --quarter 2025Q2 \
    --level 2
```

### E. Every Available Quarter

```bash
python inspect_covariance.py \
    --method bottom_up \
    --input data/daily_returns.csv \
    --return-unit decimal \
    --quarter all \
    --level all
```

To do the same for Top-Down, replace `bottom_up` with `top_down`.

### F. Custom Historical Window

For example, to use a 504-observation covariance window with a minimum of 252 observations:

```bash
python inspect_covariance.py \
    --method bottom_up \
    --input data/daily_returns.csv \
    --return-unit decimal \
    --quarter 2025Q2 \
    --level all \
    --covariance-window 504 \
    --min-obs 252
```

**Important:** Use the same window settings as the portfolio run you want to verify.

---

## 6. Optimization Hierarchies

### Bottom-Up

| Level | Optimization | Number of Nodes |
|---|---|---:|
| 1 | Regional ILB proxies | 6 |
| 2 | Global commodities | 1 |
| 3 | Four economic environments per region | 24 |
| 4 | Regional baskets | 6 |
| 5 | Global portfolio | 1 |
| | **Total** | **38** |

### Top-Down

| Level | Optimization | Number of Nodes |
|---|---|---:|
| 1 | Regional ILB proxies | 6 |
| 2 | Global ILB portfolio | 1 |
| 2 | Global commodities | 1 |
| 2 | Global equity | 1 |
| 2 | Global bonds | 1 |
| 3 | Economic environments | 4 |
| 4 | Global portfolio | 1 |
| | **Total** | **15** |

Identity mappings are not optimizations and therefore do not generate covariance files.

---

## 7. Output Structure

The default output directory is:

```text
outputs/
└── diagnostics/
    ├── bottom_up/
    │   └── 2025Q2/
    │       ├── Level_1/
    │       ├── Level_2/
    │       ├── Level_3/
    │       ├── Level_4/
    │       └── Level_5/
    │
    └── top_down/
        └── 2025Q2/
            ├── Level_1/
            ├── Level_2/
            ├── Level_3/
            └── Level_4/
```

Each optimization node produces four CSV files.

### 1. Covariance

`*_Covariance.csv`

The original covariance matrix estimated from the node's input return series.

### 2. Normalized Covariance

`*_Normalized_Covariance.csv`

The covariance matrix after division by the maximum diagonal variance.

This is the matrix used by the optimizer.

The normalization does not change risk contribution percentages because the same positive scalar is applied to every matrix element.

### 3. Weights

`*_Weights.csv`

Contains:

| Column | Meaning |
|---|---|
| Asset | Optimized input asset or proxy |
| Capital Weight | Portfolio capital allocation |
| Target Risk Contribution | Desired variance contribution |
| Actual Risk Contribution | Achieved variance contribution |

### 4. Metadata

`*_Metadata.csv`

Contains:

- Methodology.
- Quarter.
- Optimization node.
- Hierarchy level.
- Input assets.
- Historical start date.
- Historical end date.
- Number of observations.
- Covariance normalization scale.
- Objective value.
- Optimizer iterations.

---

## 8. Independently Verify Risk Contributions in Excel

The purpose of exporting these files is to independently check whether each optimization achieved its intended risk budget.

For each node, open:

1. `*_Covariance.csv`
2. `*_Weights.csv`

Use the raw covariance matrix and the capital weights.

### Step 1: Understand the calculation

Let:

- \(w\) = vector of capital weights.
- \(\Sigma\) = covariance matrix.
- \(\Sigma w\) = covariance-adjusted portfolio weights.

Portfolio variance:

\[
\sigma_p^2=w^\top\Sigma w
\]

Component variance contribution:

\[
CV_i=w_i(\Sigma w)_i
\]

Actual risk contribution:

\[
RC_i=
\frac{w_i(\Sigma w)_i}
{w^\top\Sigma w}
\]

### Step 2: Calculate in Excel

Suppose the covariance matrix is in `B2:F6` and the corresponding capital weights are in `B10:B14`.

Calculate:

**Covariance-adjusted weights:**

```excel
=MMULT(B2:F6,B10:B14)
```

**Portfolio variance:**

```excel
=SUMPRODUCT(B10:B14,MMULT(B2:F6,B10:B14))
```

**Individual risk contribution:**

```excel
=B10*MMULT(B2:F6,$B$10:$B$14)/SUMPRODUCT($B$10:$B$14,MMULT(B2:F6,$B$10:$B$14))
```

Adjust the ranges for the number of assets in each optimization.

### Step 3: Compare against exported results

Compare your calculated risk contributions against the `Actual Risk Contribution` column.

Also compare them against `Target Risk Contribution`.

For example:

| Asset | Target RC | Actual RC |
|---|---:|---:|
| Asset A | 50% | 49.8% |
| Asset B | 50% | 50.2% |

The difference reflects the optimizer's achieved solution and tolerance.

### Step 4: Check that contributions sum to 100%

\[
\sum_i RC_i=1
\]

In Excel:

```excel
=SUM(actual_risk_contribution_range)
```

The result should be approximately 1.0.

---

## 9. Important Methodological Notes

### Capital weights are not risk contributions

A 50/50 risk budget does not imply 50/50 capital allocation.

The optimizer determines capital weights to achieve the requested risk contribution targets.

### Each hierarchy node has its own covariance matrix

For example, the Bottom-Up global portfolio covariance matrix is calculated using the six regional basket proxy return series.

It is not the original 17-instrument covariance matrix.

Similarly, each regional environment has its own covariance matrix based on its two input proxy series.

### The exported covariance matrix is the actual optimization input

The diagnostic function captures the covariance matrix generated by the shared optimizer.

It does not independently reconstruct the matrix after optimization.

### Historical windows

For each quarter, the tool uses observations strictly before the quarter's effective date.

It uses complete observations and selects the most recent observations up to the specified covariance window.

Quarters without enough historical observations are skipped.

### Reproducibility

To reproduce the original portfolio optimization, use:

- The same input dataset.
- The same return units.
- The same covariance window.
- The same minimum observation requirement.
- The same optimizer implementation.

The exporter reruns the selected optimization rather than reading previously saved quarterly allocations.

---

## 10. Troubleshooting

| Issue | Possible solution |
|---|---|
| Missing instrument columns | Check the input CSV headers. |
| Invalid return units | Confirm whether returns are decimals or percentages. |
| Insufficient observations | Use a later quarter or reduce `--min-obs` if appropriate. |
| Import errors | Run commands from the project root and activate `.venv`. |
| Missing covariance diagnostics | Check that `risk_budget.py` supports `return_diagnostics=True`. |
| Unexpected weights | Verify the covariance matrix, input units, and target risk contributions. |

---

## 11. Recommended Verification Workflow

For a reliable spot check:

1. Run the normal Bottom-Up or Top-Down portfolio workflow.
2. Select a quarter from the saved quarterly weights.
3. Run `inspect_covariance.py` for that methodology and quarter.
4. Open the covariance and weights CSV files for a selected node.
5. Recalculate the risk contributions independently in Excel.
6. Compare calculated actual contributions with the exported actual contributions.
7. Compare actual contributions with the target risk budget.
8. Repeat at multiple hierarchy levels.

This provides an independent verification process for the hierarchical risk-budget optimizations.
