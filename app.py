import streamlit as st
import pandas as pd
import requests

# 🔥 CHANGE THIS AFTER DEPLOYMENT
API_URL = "https://aju-production.up.railway.app"

st.set_page_config(page_title="PDF Smart Search", layout="wide")

# ---- UI STYLE ----
st.markdown("""
<style>
body {
    background-color: #0E1117;
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 Financial PDF Smart Search")

# ---- FILE UPLOAD ----
file = st.file_uploader("Upload your PDF")

if file:
    res = requests.post(f"{API_URL}/upload", files={"file": file})

    if res.status_code == 200:
        st.success("✅ PDF uploaded & processed")
    else:
        st.error("Upload failed")


# ---- SEARCH ----
query = st.text_input("🔍 Search (example: chethana)")

if query:
    res = requests.get(f"{API_URL}/search?q={query}")
    data = res.json()

    if "results" in data:
        # df = pd.DataFrame(data["results"])

        # st.subheader("📋 Results")

        # st.dataframe(df[["date", "name", "debit", "credit", "balance"]])

        df = pd.DataFrame(data["results"])

# 🔥 FIX 1: Replace None with 0
        df = df.fillna(0)

# 🔥 FIX 2: Convert numeric columns properly
        for col in ["debit", "credit", "balance"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        st.subheader("📋 Results")

        st.dataframe(df[["date", "name", "debit", "credit", "balance"]])

        st.metric("💰 Total Credit", f"₹ {data['total_credit']:.2f}")
    else:
        st.error(data.get("error", "Something went wrong"))
