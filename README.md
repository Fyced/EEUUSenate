# Quantitative Analysis of US Senate Trading Patterns

This project implements an automated data engineering, machine learning, and quantitative backtesting pipeline designed to extract, analyze, and model the stock market transactions of United States Senate members. 

The primary objective is to identify statistically significant predictive factors (alpha) by isolating trades with the highest probability of outperforming the S&P 500. This is achieved through the analysis of variables such as sector classification, individual trading behavior, reporting latency, and broader market trends.

---

## Project Structure

The repository is organized to strictly separate raw data, extraction processes, error logs, and analytical models:

* **[Years] (e.g., 2017, 2020, 2025):** Isolated directories per year containing the raw extraction of government financial disclosures.
* **scripts/:** Contains the Python source code responsible for the ETL pipeline, data cleaning, and modeling.
* **errorsGlobal/:** Centralized error logging for bulk code executions.
* **\*.csv in the root:** Aggregated and engineered datasets (e.g., `2020-2025_ml_features.csv`) prepared for machine learning consumption.

### Annual Data Directories
Each year folder (e.g., `2025/`) acts as a closed environment for data collection for that specific period and contains:
* **errors/:** Extraction error logs specific to that year.
* **movementsPdf/:** Directory containing the original downloaded PDF documents of the Financial Disclosures.
* **{year}FD.zip** and **{year}FD.txt:** Raw compressed and text files sourced directly from Senate databases.
* **errorCurling.txt:** Log of errors generated during web requests for document downloading.
* **transacciones_extraidas{year}.csv:** The initial data dump, where text is parsed from PDFs and basic information is tabulated prior to processing.
* **{year}.csv:** The cleaned and structured dataset for that specific year.

### Core Scripts Directory
Although the final execution is consolidated in Jupyter Notebooks, the core operational scripts reside here:
* **[extraction_script_name].py:** Connects to the public registries, downloads disclosures, and parses the text to convert bureaucratic documents into tabular data.
* **[cleaning_script_name].py:** Feature engineering script that handles critical null values (e.g., imputing trade ownership), normalizes the names of over 1,000 tickers, and cross-references financial sectors.
* **[ml_notebook_name].ipynb:** The primary analytical environment where the Random Forest algorithm is trained, historical prices are fetched, and the portfolio simulation is executed.

---

## System Architecture and Methodology

The project implements an end-to-end quantitative finance pipeline, structured into the following phases:

### 1. Data Engineering (ETL) & API Handling
A robust system was developed to convert unstructured PDF documents into a standardized dataset. Additionally, a sequential download engine was implemented with randomized sleep intervals and retry logic to fetch historical prices for over 1,000 assets from the Yahoo Finance API, mitigating rate-limiting constraints.

### 2. Machine Learning & Feature Importance
A Random Forest Classifier (1,500 estimators, constrained depth) was trained to identify non-linear patterns across a dataset of over 6,000 trades. The model identified the most statistically significant predictive variables:
* **Reporting Latency (Days Difference):** Discovered a non-linear distribution where immediate reports (<5 days) or extremely delayed ones (>45 days, incurring regulatory fines) demonstrate a higher predictive correlation with positive returns.
* **Strategic Sectors:** Identified specific sectors historically prone to legislative influence (e.g., Energy and Real Estate).
* **Top Performing Profiles:** Isolated a subset of Senators with historical win rates consistently exceeding 65%.

### 3. Event-Driven Backtesting
To validate the model's out-of-sample performance, a custom event-driven portfolio simulator was developed:
* **Capital Constraints:** The simulator assumes a $10,000 initial balance, allocating $1,000 per position. Buy signals are strictly discarded if liquidity is unavailable, replicating retail trading conditions.
* **Performance Benchmarking:** The system generates a daily comparison of the strategy's total equity against an S&P 500 (SPY) Buy & Hold strategy, measuring resilience across different market regimes (including the 2022 downturn).

### 4. Key Results
Applying the optimized conditional rule set derived from the Random Forest model successfully filtered the baseline Congressional trades (which average a ~50% success rate). The refined strategy achieved a directional win rate of 66.3% over standardized 19-day holding periods.

---
*Developed in Python utilizing Pandas, Scikit-Learn, Matplotlib, and the yfinance API.*
