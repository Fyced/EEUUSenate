# U.S. Congressional Trading Analysis

An end-to-end data project that collects, structures and analyzes the stock trades disclosed by members of the **U.S. House of Representatives**, and tests whether simple, explainable filters can select trades that outperform the S&P 500.

The project covers the whole workflow:

1. Downloading the official disclosure PDFs.
2. Parsing them into a clean tabular dataset.
3. Engineering market and behavioral features.
4. Exploratory modeling with a Random Forest.
5. Simulating the resulting strategies in a capital-constrained, event-driven backtest against SPY buy & hold.

> **Note on scope:** despite the repository name (`EEUUSenate`), all data comes from the **House of Representatives** Periodic Transaction Reports (PTRs) published by the Office of the Clerk (`disclosures-clerk.house.gov`). Senate disclosures are not included.

---

## Highlights

- **Custom PDF parser for government filings.** Converts thousands of PTR PDFs into structured rows. Columns are detected dynamically from the position of each header, and transactions that span page breaks are reconstructed.
- **Resilient data collection.** Disclosure PDFs are downloaded in parallel with a thread pool. Market data and sector information for roughly 2,000 tickers are fetched from Yahoo Finance with batching, randomized delays and retries to work around rate limits.
- **Feature engineering.** Each trade gets:
  - its sector,
  - its reporting delay,
  - the market regime (SPY vs. 50-day SMA),
  - the politician's recent trading activity,
  - a "herding" signal (how many distinct members bought the same ticker in the previous 15 days).
- **Event-driven portfolio simulator.** Starts from a fixed amount of capital with a fixed position size. Signals are skipped when cash is not available, and results are compared year by year and cumulatively against SPY buy & hold.
- **Dataset.** About 12,350 purchase transactions, mostly from 2020–2025 filings, ready for further analysis.

---

## Repository structure

```
.
├── 2020-2025PP.csv           # Main dataset: purchases + engineered features (~12.3k rows)
├── 2022-2025.csv             # Cleaned transactions (all types), no engineered features (~17k rows)
├── 2026PP.csv                # 2026 filings processed with the same feature pipeline
├── scripts/
│   ├── PdfGetter.py          # Downloads the yearly filing index (ZIP) and the PTR PDFs
│   ├── extractionv2.py       # Parses PTR PDFs into a per-year CSV
│   ├── posprocesadoDatos.py  # Feature engineering (sector, market regime, activity, herding)
│   ├── basicStrategy.ipynb   # Baseline: copy every purchase, compare with SPY, rank members
│   ├── SecondStrategy.ipynb  # Random Forest, rule exploration and backtests (working version)
│   └── pointsStrategy.ipynb  # Cleaned, final version of the analysis and backtests
└── README.md
```

Raw data is generated locally and kept out of the repository through `.gitignore`. This includes the per-year folders (`2017/` … `2026/`) with the downloaded PDFs, ZIP/TXT indexes, intermediate CSVs and error logs. Running the pipeline (see [How to run](#how-to-run)) recreates the following layout for each year:

```
{year}/
├── {year}FD.zip / {year}FD.txt   # Official filing index (DocIDs) from the House Clerk
├── movementsPdf/                 # Downloaded PTR PDFs ({DocID}.pdf)
├── errors/                       # Download and extraction logs
│   ├── errorCurling.txt
│   ├── erroresExtraction.txt
│   ├── errorFechas.txt
│   └── errorAmount.txt
└── {year}.csv                    # Parsed transactions for that year
```

---

## Pipeline

### 1. Data acquisition (`PdfGetter.py`)

- Downloads `{year}FD.zip` from the House Clerk and extracts the filing index `{year}FD.txt`, which lists every document ID for that year.
- Downloads each PTR PDF (`ptr-pdfs/{year}/{DocID}.pdf`) using a `ThreadPoolExecutor` with 20 workers, a request timeout and per-document error logging.
- Includes header-only helpers (`HEAD` requests) to check the `Last-Modified` date of the current year's files, as a basis for incremental updates.

### 2. PDF extraction (`extractionv2.py`)

- Uses `pdfplumber` to locate the table headers on each page (Owner, Asset, Transaction Type, Date, Notification Date, Amount, Cap. Gains). From their positions it builds explicit column boundaries.
- Rebuilds transactions whose text is split across rows or across pages.
- For each transaction it:
  - extracts the **ticker** and the **asset type code** (e.g. `[ST]` for stocks, `[OP]` for options) from the asset description,
  - parses the **transaction date** and the **notification date**,
  - computes the **reporting delay** in days,
  - normalizes the **amount** to the official disclosure ranges and adds a numeric midpoint,
  - extracts the filer **name** and the **filing status** (`new` / `amended`).
- Malformed dates, amounts or pages are written to the per-year error logs instead of stopping the run. The function returns the number of documents that failed.

### 3. Feature engineering (`posprocesadoDatos.py`)

The script keeps only **purchases** (`Tx_Type == 'P'`) with filing status `new`, sorts them by notification date, and adds:

| Feature | Description |
|---|---|
| `Sector` | Yahoo Finance sector, or the fund category for ETFs. Lookups are sequential, with randomized delays and up to 3 retries. |
| `SPY_Trend` | 1 if SPY closed above its 50-day SMA on the notification date, 0 otherwise. Matched with `merge_asof` so that weekends and holidays fall back to the last trading day. |
| `Operaciones_Ultimos_30d` | Number of trades the same member reported in the previous 30 days. |
| `Compradores_Mismo_Ticker_15d` | Number of distinct members who reported buying the same ticker in the previous 15 days. |

The script finishes with a check that lists every ticker whose sector could not be resolved.

### 4. Analysis and modeling (`pointsStrategy.ipynb`)

- **Entry and exit:** each trade is entered on its **notification date**, when the information becomes public, and held for **19 calendar days**.
- **Target:** `Exito = 1` if the trade's 19-day return beat SPY's return over the same window.
- **Model:** a Random Forest classifier (1,500 trees, `max_depth=7`) is trained on reporting delay, amount, recent activity, herding, market regime, month, sector, member, owner and asset type. Its feature importances guide the exploration.
- **Rules:** simple, interpretable filters are then defined from per-group success rates:
  - members with at least 20 trades and a success rate of 58% or more,
  - selected sectors (Energy and Real Estate),
  - reporting delay of 5 days or less, or 45 days or more.

### 5. Backtesting (`pointsStrategy.ipynb`)

- **Yearly simulation:** each year starts with $10,000 and uses $750 per position. A signal is executed only if enough cash is free, so rejected signals are counted. Each year is compared with SPY buy & hold over the same year.
- **Continuous simulation:** a single portfolio runs from January 2020 onward and produces an equity curve plotted against SPY buy & hold.

---

## Results

All figures come from the outputs saved in the notebooks.

### Baseline: copying every purchase (`basicStrategy.ipynb`)

For 6,364 purchases from 2021–2025, entered on the notification date and held for 19 days, investing $1,000 per trade:

| | Copy all purchases | Same windows in SPY |
|---|--:|--:|
| Total P&L | $74,090 | $55,524 |
| Trades with a positive return | 55.5% | 63.5% |
| Average return per trade | 1.16% | 0.87% |

Copying every purchase outperformed the index on total and average return, but with a lower hit rate: fewer trades were winners, and the gains were concentrated in a smaller number of strong trades.

### Filtered strategies (`pointsStrategy.ipynb`)

Here, "success" means beating SPY over the 19-day holding window. The base rate across 11,205 valid trades is **48.8%**.

| Strategy | Trades | Success rate |
|---|---|---|
| All purchases (baseline) | 11,205 | 48.8% |
| Selected members only (12 members) | 727 | 65.6% |
| Energy & Real Estate only | 1,096 | 51.6% |
| Selected sectors + delay ≤5 or ≥45 days | 521 | 55.5% |
| **Combined filter** (selected members **or** sector + delay) | **1,158** | **61.7%** |

**Portfolio simulation of the combined filter**

| Year | Executed trades | Rejected (no cash) | SPY ($) | Strategy ($) | Difference ($) |
|---|---|---|---|---|---|
| 2020 | 99 | 17 | 11,724 | 10,535 | −1,189 |
| 2021 | 194 | 59 | 13,051 | 13,891 | +841 |
| 2022 | 143 | 22 | 8,135 | 12,748 | +4,613 |
| 2023 | 68 | 5 | 12,671 | 11,170 | −1,501 |
| 2024 | 59 | 133 | 12,559 | 11,100 | −1,459 |
| 2025 | 145 | 205 | 11,801 | 11,588 | −213 |

Each year starts from $10,000. Summed over all years, the strategy made $11,032 against $9,940 for SPY. Most of that edge comes from **2022**: the strategy stayed positive while the index fell.

The continuous simulation from January 2020 ends at **$27,784**, against **$22,241** for SPY buy & hold.

### What the exploration showed

- Member identity is by far the strongest separator. A small group of members consistently beat the index over 19-day windows.
- Sector and reporting delay add little on their own. Basic Materials (53.8%) and Real Estate (53.1%) were the best sectors. Reports filed within 5 days succeeded 50.2% of the time, close to the 48.8% base rate.
- The strategy's advantage depends on the year: it was strongest in the 2022 bear market and weaker in 2023–2025.

---

## Limitations

These results should be read as **exploratory and in-sample**, not as a validated trading strategy.

- **No out-of-sample validation.** The member list and the rules were chosen on the same 2020–2025 data used to evaluate them. The Random Forest is fitted on the full dataset and used only for feature importance; it is not evaluated on held-out data. Success rates are therefore optimistic.
- **Look-ahead in the baseline notebook.** In `basicStrategy.ipynb`, the trade-level returns use the *transaction* date as the entry date, and that date is only known once the trade is reported. The main analysis (`pointsStrategy.ipynb`) correctly enters on the notification date.
- **Survivorship bias.** About 100 tickers had no price data on Yahoo Finance (delisted, merged or renamed, e.g. SIVB, FRC, TWTR, ATVI), so those trades were dropped.
- **Market regime coverage.** SPY data is downloaded from 2021, so `SPY_Trend` is 0 for every trade notified before about March 2021.
- **Data quality:**
  - Member names are not fully normalized; the same person can appear under several spellings.
  - Blank `Owner` values (filer's own account) are filled with `Self`.
  - At least one row has a mis-parsed year.
  - About 9% of rows have an unknown sector.
- **Simplified execution.** The simulator ignores transaction costs, slippage and taxes. Positions are valued at cost until they close, and returns use adjusted close prices.

---

## Roadmap

- [ ] Walk-forward validation: select members and rules on past data only, then evaluate on later years.
- [ ] Evaluate the Random Forest on a time-based train/test split (precision, ROC-AUC) instead of using it only for feature importance.
- [ ] Normalize member names, for example against an official member list.
- [ ] Download SPY history from 2017 to cover the full dataset.
- [ ] Add a script that merges the yearly CSVs into the aggregated dataset.
- [ ] Add Senate disclosures (eFD) to cover the whole Congress.
- [ ] Add transaction costs and risk metrics (Sharpe ratio, max drawdown) to the backtest.

---

## How to run

### Requirements

- Python 3.10+
- Packages:

```bash
pip install pandas numpy requests pdfplumber yfinance scikit-learn matplotlib jupyter
```

### Steps

The scripts use paths relative to `scripts/`, and the year is set in each script's `__main__` block.

```bash
cd scripts

# 0. Create the folders for the year (e.g. 2025)
mkdir -p ../2025/movementsPdf ../2025/errors

# 1. Download the filing index and the PTR PDFs
#    (call getOneZip(year), then getAllPdf(year))
python PdfGetter.py

# 2. Parse the PDFs into ../{year}/{year}.csv
python extractionv2.py

# 3. Add the engineered features (edit the input/output paths in __main__)
python posprocesadoDatos.py

# 4. Run the analysis and backtests
jupyter notebook pointsStrategy.ipynb
```

Yahoo Finance applies rate limits. Downloading prices and sectors for about 2,000 tickers can take a long time, and some requests may need to be retried.

---

## Data dictionary

| Column | Description |
|---|---|
| `Pdf_Id` | Document ID of the PTR filing |
| `Owner` | Account owner: `SP` spouse, `JT` joint, `DC` dependent child, blank = filer |
| `Asset` | Asset description as written in the filing |
| `Acronym` | Ticker extracted from the asset description |
| `Op_Type` | Asset type code (e.g. `ST` stock, `OP` option) |
| `Tx_Type` | Transaction type (`P` purchase, `S` sale, …) |
| `Date` | Transaction date |
| `Notif_Date` | Notification (reporting) date |
| `Diferencia_Dias` | Reporting delay in days |
| `Amount` / `Amount_Num` | Disclosed amount range and its numeric midpoint |
| `Name` | Member of Congress |
| `Filing Status` | `new` or `amended` |
| `Sector`, `SPY_Trend`, `Operaciones_Ultimos_30d`, `Compradores_Mismo_Ticker_15d` | Engineered features (see [Feature engineering](#3-feature-engineering-posprocesadodatospy)) |

---

## Data sources

- [Office of the Clerk – Financial Disclosure Reports](https://disclosures-clerk.house.gov/): PTR PDFs and yearly filing indexes.
- [House asset type codes](https://fd.house.gov/reference/asset-type-codes.aspx)
- [Yahoo Finance](https://finance.yahoo.com/), through `yfinance`: prices, sectors and the SPY benchmark.

---

## Disclaimer

This project is for educational and research purposes only. It is not financial advice. The data comes from public disclosures and may contain parsing errors.

---

*Built with Python: pandas, NumPy, pdfplumber, requests, scikit-learn, Matplotlib and yfinance.*
