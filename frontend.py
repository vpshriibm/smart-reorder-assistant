import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Smart Reordering Assistant", layout="wide")
st.title("📦 Smart Reordering Assistant")

with st.sidebar:
    uploaded_file = st.file_uploader("Upload Sales CSV (ds, sku, y)", type=["csv"])
    stock_file = st.file_uploader("Optional: Upload Stock CSV (sku, stock)", type=["csv"])
    constraint_file = st.file_uploader("Optional: Upload Constraints CSV (sku, min_qty, stockout_risk)", type=["csv"])

    reorder_mode = st.selectbox("Reorder Trigger Mode", ["fixed", "percent_drop", "stock"])
    threshold = st.number_input("Threshold", value=50.0)
    buffer = st.number_input("Stock Buffer", value=10.0)
    budget = st.number_input("Optimization Budget", value=50000.0)
    objective = st.selectbox("Optimization Objective", ["Maximize demand", "Fair allocation"])
    run_forecast = st.button("📊 Forecast and Reorder")

# Helper for PDF export
def export_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    for i, row in df.iterrows():
        pdf.cell(200, 10, txt=str(row.to_dict()), ln=1)
    buffer = BytesIO()
    pdf.output(buffer, 'S').encode('latin1')
    buffer.seek(0)
    return buffer

# Session state
if "forecast_df" not in st.session_state:
    st.session_state["forecast_df"] = None

if run_forecast and uploaded_file:
    files = {
        "file": ("sales.csv", uploaded_file.getvalue(), "text/csv")
    }
    if stock_file:
        files["stock_file"] = ("stock.csv", stock_file.getvalue(), "text/csv")
    if constraint_file:
        files["constraint_file"] = ("constraints.csv", constraint_file.getvalue(), "text/csv")

    data = {
        "reorder_mode": reorder_mode,
        "threshold": str(threshold),
        "buffer": str(buffer)
    }

    res = requests.post("http://localhost:8000/forecast", files=files, data=data)

    if res.status_code == 200:
        result = res.json()
        st.session_state["forecast_df"] = pd.DataFrame(result["forecast"])
    else:
        st.error(f"Forecast API Error: {res.status_code} - {res.text}")

# Display forecast
forecast_df = st.session_state.get("forecast_df")
if forecast_df is not None:
    st.subheader("📈 Forecast Results")
    st.dataframe(forecast_df)

    fig = px.line(forecast_df, x="ds", y="yhat", color="sku", title="Forecast per SKU")
    st.plotly_chart(fig, use_container_width=True)

    st.download_button("⬇️ Export to CSV", forecast_df.to_csv(index=False), "forecast.csv")

    pdf_buffer = export_pdf(forecast_df)
    st.download_button("📄 Export to PDF", data=pdf_buffer.read(), file_name="forecast.pdf", mime="application/pdf")

    if st.button("🚀 Run Optimization"):
        try:
            payload = {
                "forecast": forecast_df.to_dict(orient="records"),
                "budget": budget,
                "objective": objective
            }
            res = requests.post("http://localhost:8000/optimize", json=payload)
            if res.status_code == 200:
                optimized = pd.DataFrame(res.json())
                st.subheader("🎯 Optimized Reorder Plan")
                st.dataframe(optimized)

                st.success("📧 Notifications sent!")
                st.code("SMS: Reorder triggered for risky SKUs\nEmail: Plan attached.")
            else:
                st.error(f"Optimization failed: {res.status_code} - {res.text}")
        except Exception as e:
            st.error(f"Optimization request failed: {str(e)}")
