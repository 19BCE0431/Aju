# import streamlit as st
# import requests
# import pandas as pd

# API_URL = "https://aju-production.up.railway.app"

# st.title("📊 Financial PDF Smart Search")

# # ---------------------------
# # UPLOAD
# # ---------------------------
# file = st.file_uploader("Upload your PDF")

# if file:
#     files = {"file": file.getvalue()}

#     res = requests.post(f"{API_URL}/upload", files=files)

#     if res.status_code == 200:
#         st.success("✅ PDF uploaded & processed")
#     else:
#         st.error("❌ Upload failed")


# # ---------------------------
# # SEARCH
# # ---------------------------
# query = st.text_input("🔍 Search (example: chethana)")

# if query:
#     res = requests.get(f"{API_URL}/search", params={"q": query})

#     if res.status_code == 200:
#         response = res.json()

#         data = response.get("results", [])

#         if len(data) == 0:
#             st.warning("No results found")
#         else:
#             df = pd.DataFrame(data)

#             # Ensure columns exist safely
#             for col in ["debit", "credit", "balance"]:
#                 if col in df.columns:
#                     df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

#             st.subheader("Results")
#             st.dataframe(df)

#             st.markdown(f"### 💰 Total Credit: ₹ {response.get('total_credit', 0)}")

#     else:
#         st.error("Search failed")





from __future__ import annotations

import os
from io import BytesIO

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Statement Finder",
    page_icon="PDF",
    layout="wide",
)


def get_backend_url() -> str:
    # On Streamlit Cloud, add BACKEND_URL in App settings > Secrets.
    # Example: BACKEND_URL = "https://your-app.up.railway.app"
    try:
        backend_url = st.secrets.get("BACKEND_URL")
    except Exception:
        backend_url = None
    return (backend_url or os.getenv("BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")


BACKEND_URL = get_backend_url()

st.markdown(
    """
    <style>
      .stApp {
        background:
          radial-gradient(circle at top left, rgba(245, 183, 70, .24), transparent 34rem),
          radial-gradient(circle at top right, rgba(51, 128, 86, .22), transparent 30rem),
          linear-gradient(135deg, #fff8e7 0%, #eaf7ec 58%, #deefe8 100%);
      }
      .hero {
        padding: 2.2rem 2.4rem;
        border: 1px solid rgba(255,255,255,.7);
        border-radius: 28px;
        background: rgba(255,255,255,.58);
        box-shadow: 0 24px 70px rgba(28, 64, 44, .16);
        backdrop-filter: blur(18px);
      }
      .hero h1 {
        font-size: clamp(2.4rem, 6vw, 5.4rem);
        line-height: .92;
        letter-spacing: -.06em;
        margin: 0 0 .8rem 0;
        color: #17211b;
      }
      .hero p {
        color: #58665f;
        font-size: 1.08rem;
        max-width: 780px;
      }
      .metric-card {
        padding: 1.3rem 1.5rem;
        border-radius: 22px;
        border: 1px solid rgba(255,255,255,.7);
        background: rgba(255,255,255,.62);
        box-shadow: 0 16px 46px rgba(28, 64, 44, .12);
      }
      .metric-card span {
        display:block;
        color:#64746c;
        font-weight:800;
        margin-bottom:.45rem;
      }
      .metric-card strong {
        font-size:2rem;
        color:#193b29;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>Find vendor payments from a PDF.</h1>
      <p>
        Upload your bank statement PDF, search one unique word like
        <b>chethana</b>, and get Date, Name, Debit, Credit, Balance and total Credit.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

with st.sidebar:
    st.subheader("Connection")
    st.caption("FastAPI backend running on Railway")
    st.code(BACKEND_URL)
    min_score = st.slider("Match strictness", 0, 100, 55, 5)
    limit = st.slider("Maximum rows", 10, 300, 100, 10)

uploaded_pdf = st.file_uploader("Upload PDF statement", type=["pdf"])
keyword = st.text_input("Search keyword", placeholder="Example: chethana")

search_clicked = st.button("Search PDF", type="primary", use_container_width=True)

if search_clicked:
    if uploaded_pdf is None:
        st.error("Please upload a PDF first.")
        st.stop()

    if not keyword.strip():
        st.error("Please enter a search keyword.")
        st.stop()

    with st.spinner("Reading PDF and searching transactions..."):
        try:
            files = {
                "file": (
                    uploaded_pdf.name,
                    uploaded_pdf.getvalue(),
                    "application/pdf",
                )
            }
            url = f"{BACKEND_URL}/api/extract/{keyword.strip()}"
            response = requests.post(
                url,
                files=files,
                params={"min_score": min_score, "limit": limit},
                timeout=120,
            )
        except requests.RequestException as exc:
            st.error(f"Could not connect to backend: {exc}")
            st.stop()

    if response.status_code != 200:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        st.error(f"Backend error: {detail}")
        st.stop()

    data = response.json()
    rows = data.get("matches", [])

    col1, col2, col3 = st.columns(3)
    col1.markdown(
        f'<div class="metric-card"><span>Total Credit</span><strong>₹{data["total_credit"]:,.2f}</strong></div>',
        unsafe_allow_html=True,
    )
    col2.markdown(
        f'<div class="metric-card"><span>Total Debit</span><strong>₹{data["total_debit"]:,.2f}</strong></div>',
        unsafe_allow_html=True,
    )
    col3.markdown(
        f'<div class="metric-card"><span>Matches</span><strong>{len(rows)}</strong></div>',
        unsafe_allow_html=True,
    )

    st.write("")

    if not rows:
        st.warning("No matching rows found. Try a more unique word or reduce match strictness.")
        st.stop()

    df = pd.DataFrame(rows)
    display_columns = ["date", "value_date", "name", "debit", "credit", "balance", "match_score", "page"]
    df = df[[column for column in display_columns if column in df.columns]]
    df = df.rename(
        columns={
            "date": "Date",
            "value_date": "Value Date",
            "name": "Name",
            "debit": "Debit",
            "credit": "Credit",
            "balance": "Balance",
            "match_score": "Match Score",
            "page": "Page",
        }
    )

    st.subheader("Matching transactions")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Debit": st.column_config.NumberColumn("Debit", format="₹%.2f"),
            "Credit": st.column_config.NumberColumn("Credit", format="₹%.2f"),
            "Balance": st.column_config.NumberColumn("Balance", format="₹%.2f"),
            "Match Score": st.column_config.NumberColumn("Match Score", format="%.0f"),
        },
    )

    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download results CSV",
        data=csv_buffer.getvalue(),
        file_name="statement_search_results.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("Upload a PDF, enter a keyword, then click Search PDF.")
