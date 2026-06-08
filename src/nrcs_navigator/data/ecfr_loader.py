"""Fetch the four in-scope eCFR parts and chunk them by section.

Source: the eCFR versioner API, which serves each regulation part as structured
XML at a pinned version date (config.ECFR_VERSION_DATE). The XML exposes the
part / subpart / section hierarchy explicitly, so we chunk on section boundaries
(one chunk per section) rather than on a blind character window. Each chunk
carries its program, CFR part, section number, citation, and heading, so the
eligibility_screener can cite the exact regulation it relied on.

Produces langchain Document objects for vectorstore.py to embed. A section
longer than config.CHUNK_SIZE tokens is split further (with config.CHUNK_OVERLAP
carried across the boundary), each piece keeping the section's metadata.

Fetched XML is cached under config.DATA_RAW so re-running the pipeline does not
re-hit the API.
"""

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from nrcs_navigator import config


def _cache_path(part: str):
    """Where one part's fetched XML is cached. The version date is in the name,
    so changing the pinned date fetches fresh rather than reusing a stale file."""
    return (
        config.DATA_RAW
        / f"ecfr_title{config.ECFR_TITLE}_part{part}_{config.ECFR_VERSION_DATE}.xml"
    )


def fetch_part_xml(part: str) -> str:
    """Return the eCFR XML for one part, fetching once and caching to disk.

    On a cache hit the file is read straight back; otherwise we hit the
    versioner API, raise on any HTTP error, and write the response through to
    DATA_RAW for next time.
    """
    path = _cache_path(part)
    if path.exists():
        return path.read_text(encoding="utf-8")

    url = (
        f"{config.ECFR_API_BASE}/full/{config.ECFR_VERSION_DATE}"
        f"/title-{config.ECFR_TITLE}.xml"
    )
    response = requests.get(url, params={"part": part}, timeout=60)
    response.raise_for_status()
    xml = response.text

    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    return xml


def parse_sections(xml: str, part: str, program: str) -> list[Document]:
    """Turn one part's XML into one Document per section.

    Walks every <DIV8 TYPE="SECTION">, joining its heading and paragraph text
    into the page content and attaching citation metadata. Sections with no
    substantive text (e.g. "[Reserved]") are skipped. Size capping happens later,
    in load_chunks.
    """
    soup = BeautifulSoup(xml, "xml")
    documents: list[Document] = []

    for section in soup.find_all("DIV8", attrs={"TYPE": "SECTION"}):
        number = section.get("N", "").strip()  # e.g. "1466.6"
        head = section.find("HEAD")
        heading = head.get_text(" ", strip=True) if head else ""

        paragraphs = [
            p.get_text(" ", strip=True) for p in section.find_all(["P", "FP"])
        ]
        body = "\n".join(text for text in paragraphs if text)
        if not body:
            continue

        page_content = f"{heading}\n{body}" if heading else body
        documents.append(
            Document(
                page_content=page_content,
                metadata={
                    "program": program,
                    "part": part,
                    "section": number,
                    "citation": f"{config.ECFR_TITLE} CFR {number}",
                    "heading": heading,
                },
            )
        )

    return documents


def load_chunks() -> list[Document]:
    """Fetch, parse, and size-cap every in-scope part into embed-ready chunks.

    One chunk per section, except a section longer than CHUNK_SIZE tokens, which
    is split into several chunks that all keep the section's metadata. This is
    the list vectorstore.build_index embeds.
    """
    section_docs: list[Document] = []
    for part, program in config.ECFR_PARTS.items():
        xml = fetch_part_xml(part)
        section_docs.extend(parse_sections(xml, part, program))

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    return splitter.split_documents(section_docs)
