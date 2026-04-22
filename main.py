from fastapi import FastAPI, UploadFile, File
import pdfplumber

app = FastAPI()

documents = []

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global documents
    documents = []

    import tempfile

    # Save temp file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    with pdfplumber.open(tmp_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if not row or len(row) < 6:
                        continue

                    try:
                        date = row[0]
                        name = row[1]

                        # Skip headers
                        if "Date" in str(date):
                            continue

                        # Clean values
                        debit = float(row[4].replace(",", "")) if row[4] else 0
                        credit = float(row[5].replace(",", "")) if row[5] else 0
                        balance = float(row[6].replace(",", "")) if len(row) > 6 and row[6] else 0

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


@app.get("/search")
def search(q: str):
    q = q.lower().strip()

    results = [doc for doc in documents if q in doc["name"].lower()]

    total_credit = sum(r["credit"] for r in results)

    return {
        "results": results,
        "total_credit": total_credit
    }
