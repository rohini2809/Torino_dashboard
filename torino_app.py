import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# --- Load and preprocess the Excel pollution trends ---
@st.cache_data
def load_pollution_trends():
    excel_path = "data.xlsx"  # Make sure this file is in the root directory
    pollutants = ["NO2", "SO2", "CH4", "O3", "HCHO", "CO", "AER"]
    data = {}

    def get_mean_column(cols):
        for c in cols:
            if "mean" in c.lower():
                return c
        return None

    xls = pd.ExcelFile(excel_path)
    for sheet in pollutants:
        df = pd.read_excel(xls, sheet_name=sheet)
        df.columns = [col.strip().lower() for col in df.columns]
        date_col = next((c for c in df.columns if "date" in c), None)
        mean_col = get_mean_column(df.columns)

        if date_col and mean_col:
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.rename(columns={date_col: "date", mean_col: "mean"})
            data[sheet] = df[["date", "mean"]]

    return data

# --- Trends Tab ---
def pollution_trends_tab():
    st.markdown("## 📈 Urban Pollution Trends")
    st.markdown("Analyze pollution evolution over time for key pollutants in Turin.")

    data = load_pollution_trends()
    pollutant = st.selectbox("Select pollutant to view trends:", list(data.keys()), key="trend_pollutant")
    df = data[pollutant]

    fig, ax = plt.subplots(figsize=(8, 3))
    sns.lineplot(data=df, x="date", y="mean", ax=ax, color="darkblue")
    ax.set_title(f"{pollutant} Mean Concentration Over Time", fontsize=12)
    ax.set_xlabel("Date")
    ax.set_ylabel("Mean Level")
    st.pyplot(fig)

    # SDG 11 Insight
    st.info(f"🏙️ **SDG 11 Insight for {pollutant}**\nHigh levels of {pollutant} can increase urban health risks, reduce air quality, and strain city resilience. Monitoring supports evidence-based planning for sustainable cities.")

