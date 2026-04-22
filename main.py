from fastapi import FastAPI, UploadFile, File
import fitz  # PyMuPDF
import re
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

app = FastAPI()

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

documents = []
embeddings = []
index = None


# -------- PARSE ROW --------
def parse_row(line):
    # date
    date_match = re.search(r'\d{2}/\d{2}/\d{2}', line)
    date = date_match.group() if date_match else None

    # numbers
    nums = re.findall(r'\d{1,3}(?:,\d{3})*\.\d{2}', line)
    nums = [float(n.replace(',', '')) for n in nums]

    debit, credit, balance = None, None, None

    if len(nums) >= 3:
        debit, credit, balance = nums[-3], nums[-2], nums[-1]

    # name cleanup
    name = re.sub(r'\d{2}/\d{2}/\d{2}', '', line)
    name = re.sub(r'\d{1,3}(?:,\d{3})*\.\d{2}', '', name)
    name = name.strip()

    return {
        "date": date,
        "name": name,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "text": line
    }


# -------- BUILD INDEX --------
def build_index(rows):
    global index, documents, embeddings

    documents = []
    embeddings = []

    for row in rows:
        emb = model.encode(row["text"])
        embeddings.append(emb)
        documents.append(row)

    dim = len(embeddings[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))


# -------- UPLOAD API --------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    doc = fitz.open(stream=content, filetype="pdf")

    rows = []

    for page in doc:
        text = page.get_text()
        lines = text.split("\n")

        for line in lines:
            if re.search(r'\d{2}/\d{2}/\d{2}', line):
                parsed = parse_row(line)
                rows.append(parsed)

    if len(rows) == 0:
        return {"error": "No valid rows found"}

    build_index(rows)

    return {"message": f"{len(rows)} rows processed"}


# -------- SEARCH API --------
@app.get("/search")
def search_api(q: str):
    global index

    if index is None:
        return {"error": "Upload PDF first"}

    query_emb = model.encode([q])
    D, I = index.search(np.array(query_emb), k=10)

    results = [documents[i] for i in I[0]]

    total_credit = sum([r["credit"] or 0 for r in results])

    return {
        "results": results,
        "total_credit": total_credit
    }
