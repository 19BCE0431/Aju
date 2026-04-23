import pandas as pd

data = response["results"]

if len(data) == 0:
    st.warning("No results found")
else:
    df = pd.DataFrame(data)

    # Ensure columns exist
    for col in ["debit", "credit", "balance"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    st.dataframe(df)

    st.markdown(f"### 💰 Total Credit: ₹ {response['total_credit']}")
