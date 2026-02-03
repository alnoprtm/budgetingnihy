# ===============================
# app.py
# Couple Budgeting & Itinerary App (Extended)
# Author: Alnobest Son Pratama
# ===============================

import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Couple Finance", layout="wide")nDB_PATH = "app.db"
BACKUP_DIR = "backups"
REPORT_DIR = "reports"

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# -------------------------------
# DATABASE
# -------------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS budget (
    category TEXT PRIMARY KEY,
    limit_amount REAL
)
""")
conn.commit()

# -------------------------------
# GLOBAL TIME FILTER
# -------------------------------
st.sidebar.header("Time Filter")
selected_year = st.sidebar.selectbox("Year", list(range(2020, datetime.now().year + 1)), index=datetime.now().year - 2020)
selected_month = st.sidebar.selectbox("Month", list(range(1, 13)), index=datetime.now().month - 1)

start_date = f"{selected_year}-{selected_month:02d}-01"
end_date = f"{selected_year}-{selected_month:02d}-31"

# -------------------------------
# OVER-BUDGET CHECK
# -------------------------------
budget_df = pd.read_sql("SELECT * FROM budget", conn)
expense_df = pd.read_sql(f"SELECT category, SUM(amount) total FROM expenses WHERE date BETWEEN '{start_date}' AND '{end_date}' GROUP BY category", conn)
merged = pd.merge(budget_df, expense_df, on="category", how="left").fillna(0)
over_budget = merged[merged["total"] > merged["limit_amount"]]

if not over_budget.empty:
    st.sidebar.warning("Over budget detected")

# -------------------------------
# PDF MONTHLY REPORT
# -------------------------------
def generate_pdf(year, month):
    file_path = f"{REPORT_DIR}/report_{year}_{month}.pdf"
    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"Monthly Financial Report - {month}/{year}", styles['Title']))
    story.append(Spacer(1, 12))

    income = pd.read_sql(f"SELECT SUM(amount) total FROM income WHERE date BETWEEN '{start_date}' AND '{end_date}'", conn)["total"][0] or 0
    expenses = pd.read_sql(f"SELECT SUM(amount) total FROM expenses WHERE date BETWEEN '{start_date}' AND '{end_date}'", conn)["total"][0] or 0
    savings = pd.read_sql(f"SELECT SUM(amount) total FROM savings WHERE date BETWEEN '{start_date}' AND '{end_date}'", conn)["total"][0] or 0

    story.append(Paragraph(f"Total Income: Rp {income:,.0f}", styles['Normal']))
    story.append(Paragraph(f"Total Expenses: Rp {expenses:,.0f}", styles['Normal']))
    story.append(Paragraph(f"Total Savings: Rp {savings:,.0f}", styles['Normal']))

    doc.build(story)
    return file_path

# -------------------------------
# EXPORT MANUAL
# -------------------------------
def export_excel():
    path = f"{BACKUP_DIR}/manual_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    writer = pd.ExcelWriter(path, engine="xlsxwriter")
    pd.read_sql("SELECT * FROM income", conn).to_excel(writer, "Income", index=False)
    pd.read_sql("SELECT * FROM expenses", conn).to_excel(writer, "Expenses", index=False)
    pd.read_sql("SELECT * FROM savings", conn).to_excel(writer, "Savings", index=False)
    pd.read_sql("SELECT * FROM itinerary", conn).to_excel(writer, "Itinerary", index=False)
    writer.close()
    return path

# -------------------------------
# UI EXTENSION
# -------------------------------
st.sidebar.header("Reports")
if st.sidebar.button("Generate Monthly PDF"):
    pdf_path = generate_pdf(selected_year, selected_month)
    with open(pdf_path, "rb") as f:
        st.sidebar.download_button("Download PDF", f, file_name=os.path.basename(pdf_path))

if st.sidebar.button("Export Excel"):
    excel_path = export_excel()
    with open(excel_path, "rb") as f:
        st.sidebar.download_button("Download Excel", f, file_name=os.path.basename(excel_path))
