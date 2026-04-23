from fastapi import FastAPI, UploadFile, File
import pdfplumber

app = FastAPI()

documents = []

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global documents
    documents = []

    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    with pdfplumber.open(tmp_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if not row or len(row) < 7:
                        continue

                    try:
                        date = row[0]
                        name = row[1]

                        if not date or "Date" in str(date):
                            continue

                        debit = float(row[4].replace(",", "")) if row[4] else 0
                        credit = float(row[5].replace(",", "")) if row[5] else 0
                        balance = float(row[6].replace(",", "")) if row[6] else 0

                        documents.append({
                            "date": date,
                            "name": name.strip(),
                            "debit": debit,
                            "credit": credit,
                            "balance": balance
                        })

                    except:
                        continue

    return {"message": f"{len(documents)} rows processed"}

from rapidfuzz import fuzz

@app.get("/search")
def search(q: str):
    q = q.lower().strip()

    results = []

    for doc in documents:
        name = doc.get("name", "").lower()

        # Fuzzy match instead of strict match
        score = fuzz.partial_ratio(q, name)

        if score > 70:   # threshold
            doc["score"] = score
            results.append(doc)

    # Sort best match first
    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "results": results,
        "total_credit": sum(r["credit"] for r in results)
    }

