"""
Tool: payment_estimator (table query)

Returns historical payment benchmarks for ALL conservation programs in a
specified state using the payment_rates table.

This tool is designed to provide the LLM with full funding history context
across programs and fiscal years so it can perform comparisons, trends,
and reasoning without needing multiple tool calls.

Type:
    SQL query (no live network, no LLM)

Data source:
    payment_rates table in Postgres
    (loaded by data/fips_payments.py)

Responsibilities:
    - Accept a state as input.
    - Retrieve all programs with payment data for that state.
    - Aggregate funding by program and fiscal year.
    - Compute total dollars, total instances, and average payment.
    - Return structured, LLM-friendly nested output.
    - Return a clear message when no data exists.

Input:
    {
        "state": "Iowa"
    }

Output:
    {
        "status": "success",
        "state": "Iowa",
        "programs": {
            "EQIP": [
                {
                    "fiscal_year": 2023,
                    "total_dollars_obligated": 12345678.90,
                    "total_instances": 5000,
                    "average_payment_per_instance": 2469.34
                }
            ],
            "ACEP": [
                {
                    "fiscal_year": 2024,
                    "total_dollars_obligated": 9876543.21,
                    "total_instances": 120,
                    "average_payment_per_instance": 82304.53
                }
            ]
        }
    }
"""

from langchain_core.tools import tool
from sqlalchemy import text

from nrcs_navigator.data import db


def get_payment_estimate_by_state(state: str) -> dict:
    """
    Retrieve all payment benchmarks for all programs in a given state.
    """

    try:

        state = state.title()

        sql = text(
            """
            SELECT
                program,
                fiscal_year,

                SUM(dollars_obligated) AS total_dollars_obligated,
                SUM(instance_count) AS total_instances,

                ROUND(
                    SUM(dollars_obligated)
                    / NULLIF(SUM(instance_count), 0),
                    2
                ) AS average_payment_per_instance

            FROM payment_rates
            WHERE state = :state

            GROUP BY program, fiscal_year
            ORDER BY program, fiscal_year
            """
        )

        with db.get_engine().connect() as conn:

            rows = conn.execute(
                sql,
                {"state": state},
            ).mappings().all()

        if not rows:

            return {
                "status": "not_found",
                "state": state,
                "programs": {},
                "message": "No payment data found for this state.",
            }

        programs = {}

        for row in rows:

            program = row["program"]

            if program not in programs:
                programs[program] = []

            programs[program].append(
                {
                    "fiscal_year": int(row["fiscal_year"]),
                    "total_dollars_obligated": float(
                        row["total_dollars_obligated"]
                    ),
                    "total_instances": int(
                        row["total_instances"]
                    ),
                    "average_payment_per_instance": float(
                        row["average_payment_per_instance"]
                    ),
                }
            )

        return {
            "status": "success",
            "state": state,
            "programs": programs,
        }

    except Exception as e:

        return {
            "status": "error",
            "state": state,
            "message": str(e),
            "programs": {},
        }


@tool
def payment_estimator(state: str) -> dict:
    """
    Retrieve historical payment benchmarks for ALL conservation
    programs in a specified state.
    """

    return get_payment_estimate_by_state(state)


if __name__ == "__main__":

    import json

    result = get_payment_estimate_by_state("Iowa")

    print(json.dumps(result, indent=2))