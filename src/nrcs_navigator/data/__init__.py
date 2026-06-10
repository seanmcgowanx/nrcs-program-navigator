"""Data pipeline package.

Building blocks invoked by notebooks/01_data_pipeline.ipynb to prepare every
data artifact the agent needs before it can answer a single question:

    db              PostgreSQL + pgvector connection, extension, and schema.
    fips_payments   Load the NRCS Practice FIPS CSV into the payment_rates table.
    ecfr_loader     Download, extract, and chunk the four eCFR regulation PDFs.
    vectorstore     Embed the eCFR chunks into the pgvector store.

These run at pipeline build time, not at agent query time. All three persist
into one Postgres database (payment_rates table, embeddings, and later the
agent checkpointer).
"""
