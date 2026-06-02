"""Download, extract, and chunk the eCFR regulation PDFs.

Source: four eCFR parts, fetched once at pipeline build time and saved to
data/raw. Produces the text chunks that vectorstore.py embeds for the
eligibility_screener RAG tool.

In scope regulations:
    7 CFR Part 1466  EQIP
    7 CFR Part 1468  ACEP
    7 CFR Part 1470  CSP
    7 CFR Part 1464  RCPP
    (7 CFR Part 1410 CRP is intentionally excluded; FSA administered.)

Intended responsibilities:
    - Fetch each regulation PDF (or load it from data/raw if already present).
    - Extract text with pypdf.
    - Split text into overlapping chunks sized for embedding (chunk size and
      overlap read from config).
    - Attach metadata to each chunk (program name, CFR part, section) so the
      eligibility_screener can cite its source.
    - Return the list of chunks for vectorstore.py to embed.
"""
