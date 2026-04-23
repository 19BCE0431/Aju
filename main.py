# from fastapi import FastAPI, UploadFile, File
# import fitz  # PyMuPDF
# import re
# from rapidfuzz import fuzz

# app = FastAPI()

# documents = []

# # ---------------------------
# # PARSE FUNCTION (CLEAN)
# # ---------------------------
# def parse_row(text):
#     text = " ".join(text.split())

#     # Skip header rows
#     if "date" in text.lower() and "balance" in text.lower():
#         return None

#     # Extract date
#     date_match = re.search(r"\d{2}/\d{2}/\d{2}", text)
#     if not date_match:
#         return None

#     date = date_match.group()

#     # numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d{2})?", text)
#     # numbers = [float(n.replace(",", "")) for n in numbers]


#     # debit, credit, balance = 0, 0, 0

#     # if len(numbers) >= 2:
#     #     balance = numbers[-1]
    
#     #     # Transaction amount is second last
#     #     txn = numbers[-2]
    
#     #     # Decide debit/credit using keywords
#     #     if any(x in text.lower() for x in ["upi", "pay", "purchase", "debit"]):
#     #         debit = txn
#     #     else:
#     #         credit = txn

#     # numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d{2})?", text)
#     # numbers = [float(n.replace(",", "")) for n in numbers]
    
#     # debit, credit, balance = 0, 0, 0
    
#     # if len(numbers) >= 2:
#     #     balance = numbers[-1]
#     #     txn = numbers[-2]
    
#     #     # 🔥 KEY LOGIC
#     #     # If only 2 numbers → assume credit
#     #     if len(numbers) == 2:
#     #         credit = txn
#     #     else:
#     #         # If 3+ numbers → assume format has both debit & credit
#     #         debit = numbers[-3]
#     #         credit = txn

#     numbers = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", text)
#     numbers = [float(n.replace(",", "")) for n in numbers]
    
#     debit, credit, balance = 0, 0, 0
    
#     if len(numbers) >= 2:
#         balance = numbers[-1]
#         txn = numbers[-2]
    
#         # Since PDF loses column structure:
#         # assume single amount = credit (safe default)
#         credit = txn

#     # Clean name
#     name = text
#     name = re.sub(r"\d{2}/\d{2}/\d{2}", "", name)
#     name = re.sub(r"\d{1,3}(?:,\d{3})*\.\d{2}", "", name)
#     name = re.sub(r"\b\d+\b", "", name)
#     name = re.sub(r"[^\w\s]", "", name)
#     name = " ".join(name.split())

#     if len(name) < 3:
#         return None

#     return {
#         "date": date,
#         "name": name,
#         "debit": debit,
#         "credit": credit,
#         "balance": balance,
#         "text": text.lower()
#     }


# # ---------------------------
# # UPLOAD API
# # ---------------------------
# @app.post("/upload")
# async def upload(file: UploadFile = File(...)):
#     global documents
#     documents = []

#     content = await file.read()
#     doc = fitz.open(stream=content, filetype="pdf")

#     lines = []

#     for page in doc:
#         text = page.get_text()
#         lines.extend(text.split("\n"))

#     current_block = ""

#     for line in lines:
#         line = line.strip()
#         if not line:
#             continue

#         # New transaction starts with date
#         if re.match(r"\d{2}/\d{2}/\d{2}", line):
#             if current_block:
#                 parsed = parse_row(current_block)
#                 if parsed:
#                     documents.append(parsed)

#             current_block = line
#         else:
#             current_block += " " + line

#     # Last block
#     if current_block:
#         parsed = parse_row(current_block)
#         if parsed:
#             documents.append(parsed)

#     return {"message": f"{len(documents)} rows processed"}


# # ---------------------------
# # SEARCH API (FUZZY)
# # ---------------------------
# @app.get("/search")
# def search(q: str):
#     q = q.lower().strip()

#     results = []

#     for doc in documents:
#         name = doc.get("name", "").lower()

#         score = fuzz.partial_ratio(q, name)

#         if score > 70:
#             doc["score"] = score
#             results.append(doc)

#     results.sort(key=lambda x: x["score"], reverse=True)

#     return {
#         "results": results,
#         "total_credit": sum(r["credit"] for r in results)
#     }















from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path
from typing import Annotated

import pdfplumber
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from rapidfuzz import fuzz


app = FastAPI(
    title="PDF Statement Search API",
    description="Upload a PDF bank statement and search transaction names.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
AMOUNT_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{2,3})+|\d+)\.\d{2}(?!\d)")

# In-memory cache is simple and fine for a small demo.
# For production, store extracted rows in Postgres/Redis.
PDF_CACHE: dict[str, list["ExtractedRow"]] = {}


class ExtractedRow(BaseModel):
    date: str
    value_date: str | None = None
    name: str
    debit: float | None = None
    credit: float | None = None
    balance: float | None = None
    page: int
    match_score: float | None = Field(default=None, ge=0, le=100)


class PhysicalLine(BaseModel):
    page: int
    page_width: float
    text: str
    words: list[dict]


class UploadResponse(BaseModel):
    session_id: str
    rows_found: int
    message: str


class SearchResponse(BaseModel):
    query: str
    session_id: str
    matches: list[ExtractedRow]
    total_debit: float
    total_credit: float
    total_balance_shown: float | None


@app.get("/")
def home() -> dict[str, str]:
    return {
        "message": "PDF Statement Search API is running.",
        "docs": "/docs",
        "upload": "POST /api/upload",
        "search": "GET /api/search/{query}?session_id=...",
        "one_call": "POST /api/extract/{query}",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: Annotated[UploadFile, File(...)]) -> UploadResponse:
    raw_pdf = await _read_pdf_upload(file)
    session_id = hashlib.sha256(raw_pdf).hexdigest()[:16]
    rows = _extract_rows_from_bytes(raw_pdf)
    PDF_CACHE[session_id] = rows

    return UploadResponse(
        session_id=session_id,
        rows_found=len(rows),
        message="PDF processed. Search with /api/search/{query}?session_id=...",
    )


@app.get("/api/search/{query}", response_model=SearchResponse)
def search_uploaded_pdf(
    query: str,
    session_id: Annotated[str, Query(description="session_id returned by /api/upload")],
    limit: Annotated[int, Query(ge=1, le=300)] = 100,
    min_score: Annotated[int, Query(ge=0, le=100)] = 55,
) -> SearchResponse:
    rows = PDF_CACHE.get(session_id)
    if rows is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Upload the PDF again, then search.",
        )
    return _search_rows(rows, query, session_id, limit, min_score)


@app.post("/api/extract/{query}", response_model=SearchResponse)
async def upload_and_search_once(
    query: str,
    file: Annotated[UploadFile, File(...)],
    limit: Annotated[int, Query(ge=1, le=300)] = 100,
    min_score: Annotated[int, Query(ge=0, le=100)] = 55,
) -> SearchResponse:
    """Best endpoint for Streamlit: upload PDF and search in one request."""
    raw_pdf = await _read_pdf_upload(file)
    session_id = hashlib.sha256(raw_pdf).hexdigest()[:16]
    rows = _extract_rows_from_bytes(raw_pdf)
    PDF_CACHE[session_id] = rows
    return _search_rows(rows, query, session_id, limit, min_score)


async def _read_pdf_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    raw_pdf = await file.read()
    if not raw_pdf:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
    return raw_pdf


def _extract_rows_from_bytes(raw_pdf: bytes) -> list[ExtractedRow]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(raw_pdf)
        tmp.flush()
        rows = extract_statement_rows(Path(tmp.name))

    if not rows:
        raise HTTPException(
            status_code=422,
            detail=(
                "No statement rows detected. If this PDF is scanned/image-only, "
                "run OCR first or use an OCR-capable document service."
            ),
        )
    return rows


def extract_statement_rows(pdf_path: Path) -> list[ExtractedRow]:
    physical_lines = _extract_physical_lines(pdf_path)
    blocks = _merge_wrapped_transaction_lines(physical_lines)

    rows: list[ExtractedRow] = []
    for block in blocks:
        row = _parse_transaction_block(block)
        if row is not None:
            rows.append(row)
    return rows


def _extract_physical_lines(pdf_path: Path) -> list[PhysicalLine]:
    lines: list[PhysicalLine] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                keep_blank_chars=False,
                use_text_flow=True,
                x_tolerance=2,
                y_tolerance=4,
            )
            grouped: dict[int, list[dict]] = {}
            for word in words:
                y_bucket = round(float(word["top"]) / 4)
                grouped.setdefault(y_bucket, []).append(word)

            for y_bucket in sorted(grouped):
                line_words = sorted(grouped[y_bucket], key=lambda item: float(item["x0"]))
                text = " ".join(word["text"] for word in line_words).strip()
                if text:
                    lines.append(
                        PhysicalLine(
                            page=page_index,
                            page_width=float(page.width),
                            text=text,
                            words=line_words,
                        )
                    )

    return lines


def _merge_wrapped_transaction_lines(lines: list[PhysicalLine]) -> list[list[PhysicalLine]]:
    blocks: list[list[PhysicalLine]] = []
    current: list[PhysicalLine] = []

    for line in lines:
        starts_transaction = bool(DATE_RE.match(line.text.strip()))
        if starts_transaction:
            if current:
                blocks.append(current)
            current = [line]
        elif current and _looks_like_continuation(line.text):
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


def _looks_like_continuation(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    skip_terms = (
        "statement",
        "opening balance",
        "closing balance",
        "date particulars",
        "withdrawals deposits balance",
    )
    return not any(term in lowered for term in skip_terms)


def _parse_transaction_block(block: list[PhysicalLine]) -> ExtractedRow | None:
    first_line = block[0]
    full_text = " ".join(line.text for line in block)
    dates = DATE_RE.findall(full_text)
    if not dates:
        return None

    amounts_by_column = _amounts_by_column(block)
    fallback_amounts = [_to_float(match.group()) for match in AMOUNT_RE.finditer(full_text)]

    debit = amounts_by_column.get("debit")
    credit = amounts_by_column.get("credit")
    balance = amounts_by_column.get("balance")

    if balance is None and fallback_amounts:
        balance = fallback_amounts[-1]

    if debit is None and credit is None and len(fallback_amounts) >= 2:
        # In many bank statements, the second-last amount is debit/credit
        # and the last amount is balance.
        credit = fallback_amounts[-2]

    name = _clean_name(full_text, dates)
    if not name or _looks_like_header(name):
        return None

    return ExtractedRow(
        date=dates[0],
        value_date=dates[1] if len(dates) > 1 else None,
        name=name,
        debit=debit,
        credit=credit,
        balance=balance,
        page=first_line.page,
    )


def _amounts_by_column(block: list[PhysicalLine]) -> dict[str, float]:
    parsed: dict[str, float] = {}

    for line in block:
        for word in line.words:
            text = str(word["text"])
            if not AMOUNT_RE.fullmatch(text):
                continue

            center_ratio = (float(word["x0"]) + float(word["x1"])) / 2 / line.page_width
            amount = _to_float(text)

            # These ranges match the common statement layout:
            # left/middle text, then debit, credit, balance at the far right.
            if 0.72 <= center_ratio < 0.83:
                parsed["debit"] = amount
            elif 0.83 <= center_ratio < 0.92:
                parsed["credit"] = amount
            elif center_ratio >= 0.92:
                parsed["balance"] = amount

    return parsed


def _search_rows(
    rows: list[ExtractedRow],
    query: str,
    session_id: str,
    limit: int,
    min_score: int,
) -> SearchResponse:
    cleaned_query = _normalise(query)
    if not cleaned_query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    scored: list[tuple[float, ExtractedRow]] = []
    for row in rows:
        haystack = _normalise(row.name)
        token_score = fuzz.partial_token_set_ratio(cleaned_query, haystack)
        substring_bonus = 100 if cleaned_query in haystack else 0
        score = max(token_score, substring_bonus)

        if score >= min_score:
            scored.append((score, row.model_copy(update={"match_score": round(score, 2)})))

    scored.sort(key=lambda item: item[0], reverse=True)
    matches = [row for _, row in scored[:limit]]

    return SearchResponse(
        query=query,
        session_id=session_id,
        matches=matches,
        total_debit=round(sum(row.debit or 0 for row in matches), 2),
        total_credit=round(sum(row.credit or 0 for row in matches), 2),
        total_balance_shown=matches[-1].balance if matches else None,
    )


def _clean_name(text: str, dates: list[str]) -> str:
    cleaned = text
    for date in dates:
        cleaned = cleaned.replace(date, " ")
    cleaned = AMOUNT_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\b\d{8,}\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:")
    return cleaned


def _looks_like_header(name: str) -> bool:
    lowered = name.lower()
    header_terms = ("particulars", "withdrawals", "deposits", "balance", "narration")
    return sum(term in lowered for term in header_terms) >= 2


def _normalise(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _to_float(value: str) -> float:
    return float(value.replace(",", ""))
