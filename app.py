# import streamlit as st
# import requests
# import pandas as pd

# # sd

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




import streamlit as st
import requests
import pandas as pd

API_URL = "https://aju-production.up.railway.app"

st.title("📊 Financial PDF Smart Search")

file = st.file_uploader("Upload your PDF")

if file:
    files = {"file": file.getvalue()}
    res = requests.post(f"{API_URL}/upload", files=files)

    if res.status_code == 200:
        st.success("✅ PDF uploaded & processed")
    else:
        st.error("❌ Upload failed")

query = st.text_input("🔍 Search (example: chethana)")

if query:
    res = requests.get(f"{API_URL}/search", params={"q": query})

    if res.status_code == 200:
        response = res.json()
        data = response.get("results", [])

        if not data:
            st.warning("No results found")
        else:
            df = pd.DataFrame(data)

            for col in ["debit", "credit", "balance"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            st.subheader("Results")
            st.dataframe(df)

            st.markdown(f"### 💰 Total Credit: ₹ {response.get('total_credit', 0)}")

    else:
        st.error("Search failed")
