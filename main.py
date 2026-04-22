from fastapi import FastAPI, UploadFile, File
import fitz
import re
from rapidfuzz import fuzz

app = FastAPI()

documents = []

def parse_row(text):
    import re

    # Remove extra spaces
    text = " ".join(text.split())

    # Extract date
    date_match = re.search(r"\d{2}/\d{2}/\d{2}", text)
    date = date_match.group() if date_match else ""

    # Extract all numbers (amounts)
    numbers = re.findall(r"\d{1,3}(?:,\d{3})*(?:\.\d{2})", text)
    numbers = [float(n.replace(",", "")) for n in numbers]

    debit = 0
    credit = 0
    balance = 0

    if len(numbers) == 2:
        # Could be debit OR credit + balance
        if numbers[0] < numbers[1]:
            debit = numbers[0]
        else:
            credit = numbers[0]
        balance = numbers[1]

    elif len(numbers) == 3:
        debit = numbers[0]
        credit = numbers[1]
        balance = numbers[2]

    # Remove date + numbers to get name
    name = re.sub(r"\d{2}/\d{2}/\d{2}", "", text)
    for num in numbers:
        name = name.replace(f"{num:,.2f}", "")
        name = name.replace(str(int(num)), "")

    name = name.strip()

    return {
        "date": date,
        "name": name,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "text": text
    }

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global documents
    documents = []

    import fitz
    import re

    content = await file.read()
    doc = fitz.open(stream=content, filetype="pdf")

    lines = []

    for page in doc:
        text = page.get_text()
        lines.extend(text.split("\n"))

    current_block = ""

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # If new date starts → process previous block
        if re.match(r'\d{2}/\d{2}/\d{2}', line):
            if current_block:
                parsed = parse_row(current_block)
                if parsed["date"] == "" or "Date" in parsed["text"]:
                    continue

                print("BLOCK:", current_block)
                print("PARSED:", parsed)
                print("------")
                documents.append(parsed)

            current_block = line
        else:
            current_block += " " + line


    # last block
    if current_block:
        parsed = parse_row(current_block)
        documents.append(parsed)

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
