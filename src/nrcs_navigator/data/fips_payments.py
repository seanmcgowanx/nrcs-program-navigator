"""Load the NRCS Practice FIPS payment CSV into the payment_rates table.

Source: NRCS Practice FIPS CSV covering FY2023 to FY2025. Powers the
payment_estimator tool for EQIP, CSP, and RCPP. The cleaned data lands in the
Postgres payment_rates table (see data/db.py), not a flat file.

Intended responsibilities:
    - Read the raw CSV from data/raw into a pandas DataFrame.
    - Normalize column names and types (practice code, program, state/FIPS,
      payment rate, fiscal year).
    - Filter to the in scope programs (EQIP Farm Bill, EQIP IRA, CStwP Farm
      Bill, CStwP IRA, CSP-GCI, RCPP-CSP, RCPP-EQIP). Legacy programs (AWEP,
      WHIP, AMA) are harmless to leave in; the agent never queries them.
    - Write the cleaned rows into the payment_rates table in Postgres via the
      shared SQLAlchemy engine.
    - Provide a query helper the payment_estimator tool can call to retrieve
      payment ranges by practice code, program, and state (SQL query).

Note: ACEP payments are appraisal based and have no rate table here. ACEP is
screened for eligibility elsewhere and redirected to the local NRCS office.
"""
