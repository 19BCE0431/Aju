from fastapi import FastAPI, UploadFile, File
import fitz
import re
from rapidfuzz import fuzz

app = FastAPI()

documents = []


def parse_row(line):
    import re

    # date
    date_match = re.search(r'\d{2}/\d{2}/\d{2}', line)
    date = date_match.group() if date_match else None

    # extract numbers
    nums = re.findall(r'\d{1,3}(?:,\d{3})*\.\d{2}', line)
    nums = [float(n.replace(',', '')) for n in nums]

    debit, credit, balance = None, None, None

    if len(nums) == 3:
        debit, credit, balance = nums[-3], nums[-2], nums[-1]

    elif len(nums) == 2:
        credit, balance = nums[-2], nums[-1]

    elif len(nums) == 1:
        balance = nums[-1]

    # extract name
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


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global documents
    documents = []

    content = await file.read()
    doc = fitz.open(stream=content, filetype="pdf")

    for page in doc:
        text = page.get_text()
        lines = text.split("\n")

        for line in lines:
            if re.search(r'\d{2}/\d{2}/\d{2}', line):
                documents.append(parse_row(line))

    return {"message": f"{len(documents)} rows processed"}


@app.get("/search")
def search_api(q: str):
    if not documents:
        return {"error": "Upload PDF first"}

    scored = []
    for doc in documents:
        score = fuzz.partial_ratio(q.lower(), doc["text"].lower())
        scored.append((score, doc))

    scored.sort(reverse=True, key=lambda x: x[0])

    results = [item[1] for item in scored[:10]]

    total_credit = sum([r["credit"] or 0 for r in results])

    return {
        "results": results,
        "total_credit": total_credit
    }
