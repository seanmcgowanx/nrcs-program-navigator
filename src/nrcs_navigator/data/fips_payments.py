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

import pandas as pd

from nrcs_navigator import config

# The NRCS programs the agent screens for. CStwP is the Conservation Stewardship
# Program (CSP); CSP-GCI is its Grassland Conservation Initiative. AMA, AWEP, and
# WHIP are legacy and dropped here so the payment_rates table only holds programs
# the agent can actually act on.
IN_SCOPE_PROGRAMS = {
    "EQIP Farm Bill",
    "EQIP IRA",
    "CStwP Farm Bill",
    "CStwP IRA",
    "CSP-GCI",
    "RCPP-CSP",
    "RCPP-EQIP",
}


def load_raw() -> pd.DataFrame:
    """Read the raw FIPS payment CSV from data/raw into a DataFrame.

    The export is not a plain CSV: it is UTF-16 encoded, tab-delimited, and
    carries a one line title ("State v. County v. CD") above the real header
    row, so we skip that first line. This returns the data exactly as shipped;
    column normalization and filtering happen in later steps.
    """
    return pd.read_csv(
        config.FIPS_PAYMENTS_CSV,
        encoding="utf-16",
        sep="\t",
        skiprows=1,
    )


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize the raw FIPS export into payment_rates-ready rows.

    The export is state-level (COUNTY/CD is always "Total"), so a row is one
    program / practice / fiscal year total for a state. Cleaning steps:

        - Drop "Total" rows in PRACTICE NAME (per-program subtotals).
        - Drop suppressed rows, where DOLLARS OBLIGATED and PRACTICE INSTANCE
          COUNT are blank (flagged "(supp)" in the unnamed trailing column).
          With no dollars they cannot inform a payment estimate.
        - Keep only IN_SCOPE_PROGRAMS.
        - Split the practice code out of PRACTICE NAME, which carries it as a
          trailing parenthetical, e.g. "Brush Management (314)".
        - Strip "$" and "," and cast the money and count columns to numbers.
        - Derive avg_payment_per_instance (dollars / instances) so the
          estimator can summarize a payment range per practice.
        - Drop the carrier columns (COUNTY/CD, INDEX(), the "(supp)" flag) and
          rename the rest to snake_case.

    Returns a fresh DataFrame; the input is not mutated.
    """
    df = raw.copy()

    df = df[df["PRACTICE NAME"] != "Total"]
    df = df[df["DOLLARS OBLIGATED"].notna()]
    df = df[df["PROGRAM"].isin(IN_SCOPE_PROGRAMS)]

    df["practice_code"] = df["PRACTICE NAME"].str.extract(r"\(([^)]+)\)\s*$")[0].str.strip()
    df["practice_name"] = (
        df["PRACTICE NAME"].str.replace(r"\s*\([^)]+\)\s*$", "", regex=True).str.strip()
    )

    df["dollars_obligated"] = (
        df["DOLLARS OBLIGATED"].str.replace(r"[$,]", "", regex=True).astype(int)
    )
    df["instance_count"] = (
        df["PRACTICE INSTANCE COUNT"].str.replace(",", "", regex=False).astype(int)
    )
    df["avg_payment_per_instance"] = (
        df["dollars_obligated"] / df["instance_count"]
    ).round(2)

    df = df.rename(
        columns={"STATE": "state", "PROGRAM": "program", "FISCAL YEAR": "fiscal_year"}
    )
    return df[
        [
            "state",
            "program",
            "practice_code",
            "practice_name",
            "fiscal_year",
            "instance_count",
            "dollars_obligated",
            "avg_payment_per_instance",
        ]
    ].reset_index(drop=True)


def load_clean() -> pd.DataFrame:
    """Convenience: read the raw CSV and return the cleaned DataFrame."""
    return clean(load_raw())
