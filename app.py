# ===============================
# app.py
# Couple Budgeting & Itinerary App (FINAL)
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
st.set_page_config(page_title="Couple Finance", layout="wide")

DB_PATH = "app.db"
BACKUP_DIR = "backups"
REPORT_DIR = "reports"

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# -------------------------------
# DATABASE CONNECTION
# -------------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# -------------------------------
# TABLES
# -------------------------------
c.execute("""
CREATE TABLE IF NOT EXISTS income (
    date TEXT,
    account TEXT,
    source TEXT,
    amount REAL,
    contributor TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    date TEXT,
    category TEXT,
    amount REAL,
    account TEXT,
    itinerary TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS savings (
    date TEXT,
    amount REAL,
    account TEXT,
    note TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS itinerary (
    date TEXT,
    activity TEXT,
    planned_budget REAL,
    actual_expense REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS budget (
    category TEXT PRIMARY KEY,
    limit_amount REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

conn.commit()

# -------------------------------
# AUTH (PIN)
# -------------------------------
def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def get_setting(key):
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else None

def set_setting(key, value):
    c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
    conn.commit()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

stored_pin = get_setting("pin_hash")

if not stored_pin:
    st.title("Set PIN")
    pin = st.text_input("Create PIN", type="password")
    if st.button("Save PIN"):
        set_setting("pin_hash", hash_pin(pin))
        st.success("PIN saved. Reload the app.")
    st.stop()

if not st.session_state.authenticated:
    st.title("Login")
    pin = st.text_input("Enter PIN", type="password")
    if st.button("Login"):
        if hash_pin(pin) == stored_pin:
            st.session_state.authenticated = True
        else:
            st.error("Wrong PIN")
    st.stop()

# -------------------------------
# GLOBAL TIME FILTER
# -------------------------------
st.sidebar.header("Time Filter")

current_year = datetime.now().year
current_month = datetime.now().month

year = st.sidebar.selectbox("Year", list(range(2020, current_year + 1)), index=current_year - 2020)
month = st.sidebar.selectbox("Month", list(range(1, 13)), index=current_month - 1)

start_date = f"{year}-{month:02d}-01"
end_date = f"{year}-{month:02d}-31"

# -------------------------------
# AUTO MONTHLY BACKUP
# -------------------------------
backup_key = f"backup_{year}_{month}"

if not get_setting(backup_key):
    path = f"{BACKUP_DIR}/backup_{year}_{month}.xlsx"
    writer = pd.ExcelWriter(path, engine="xlsxwriter")

    pd.read_sql("SELECT * FROM income", conn).to_excel(writer, "Income", index=False)
    pd.read_sql("SELECT * FROM expenses", conn).to_excel(writer, "Expenses", index=False)
    pd.read_sql("SELECT * FROM savings", conn).to_excel(writer, "Savings", index=False)
    pd.read_sql("SELECT * FROM itinerary", conn).to_excel(writer, "Itinerary", index=False)

    writer.close()
    set_setting(backup_key, "done")

# -------------------------------
# OVER-BUDGET CHECK
# -------------------------------
budget_df = pd.read_sql("SELECT * FROM budget", conn)
expense_df = pd.read_sql(
    f"""
    SELECT category, SUM(amount) total
    FROM expenses
    WHERE date BETWEEN '{start_date}' AND '{end_date}'
    GROUP BY category
    """,
    conn
)

merged = pd.merge(budget_df, expense_df, on="category", how="left").fillna(0)
over_budget = merged[merged["total"] > merged["limit_amount"]]

if not over_budget.empty:
    st.sidebar.warning("Over-budget detected")

# -------------------------------
# PDF REPORT
# -------------------------------
def generate_pdf():
    file_path = f"{REPORT_DIR}/report_{year}_{month}.pdf"
    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    story = []

    income = pd.read_sql(
        f"SELECT SUM(amount) total FROM income WHERE date BETWEEN '{start_date}' AND '{end_date}'",
        conn
    )["total"][0] or 0

    expenses = pd.read_sql(
        f"SELECT SUM(amount) total FROM expenses WHERE date BETWEEN '{start_date}' AND '{end_date}'",
        conn
    )["total"][0] or 0

    savings = pd.read_sql(
        f"SELECT SUM(amount) total FROM savings WHERE date BETWEEN '{start_date}' AND '{end_date}'",
        conn
    )["total"][0] or 0

    story.append(Paragraph(f"Monthly Report {month}/{year}", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Total Income: Rp {income:,.0f}", styles["Normal"]))
    story.append(Paragraph(f"Total Expenses: Rp {expenses:,.0f}", styles["Normal"]))
    story.append(Paragraph(f"Total Savings: Rp {savings:,.0f}", styles["Normal"]))

    doc.build(story)
    return file_path

# -------------------------------
# MANUAL EXPORT
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
# UI
# -------------------------------
st.title("Couple Budgeting & Itinerary App")

menu = st.sidebar.radio(
    "Menu",
    ["Dashboard", "Income", "Expenses", "Savings", "Itinerary", "Reports"]
)

if menu == "Income":
    st.header("Income")
    with st.form("income_form"):
        date = st.date_input("Date")
        account = st.text_input("Account")
        source = st.text_input("Source")
        amount = st.number_input("Amount", min_value=0.0)
        contributor = st.selectbox("Contributor", ["You", "Partner"])
        if st.form_submit_button("Add"):
            c.execute(
                "INSERT INTO income VALUES (?,?,?,?,?)",
                (date, account, source, amount, contributor)
            )
            conn.commit()
    st.dataframe(pd.read_sql("SELECT * FROM income", conn))

elif menu == "Expenses":
    st.header("Expenses")
    with st.form("expense_form"):
        date = st.date_input("Date")
        category = st.text_input("Category")
        amount = st.number_input("Amount", min_value=0.0)
        account = st.text_input("Account")
        itinerary = st.text_input("Itinerary")
        if st.form_submit_button("Add"):
            c.execute(
                "INSERT INTO expenses VALUES (?,?,?,?,?)",
                (date, category, amount, account, itinerary)
            )
            conn.commit()
    st.dataframe(pd.read_sql("SELECT * FROM expenses", conn))

elif menu == "Savings":
    st.header("Savings")
    with st.form("savings_form"):
        date = st.date_input("Date")
        amount = st.number_input("Amount", min_value=0.0)
        account = st.text_input("Account")
        note = st.text_input("Note")
        if st.form_submit_button("Add"):
            c.execute(
                "INSERT INTO savings VALUES (?,?,?,?)",
                (date, amount, account, note)
            )
            conn.commit()
    st.dataframe(pd.read_sql("SELECT * FROM savings", conn))

elif menu == "Itinerary":
    st.header("Itinerary")
    with st.form("itinerary_form"):
        date = st.date_input("Date")
        activity = st.text_input("Activity")
        planned = st.number_input("Planned Budget", min_value=0.0)
        actual = st.number_input("Actual Expense", min_value=0.0)
        if st.form_submit_button("Add"):
            c.execute(
                "INSERT INTO itinerary VALUES (?,?,?,?)",
                (date, activity, planned, actual)
            )
            conn.commit()
    st.dataframe(pd.read_sql("SELECT * FROM itinerary", conn))

elif menu == "Reports":
    st.header("Reports")
    if st.button("Generate Monthly PDF"):
        pdf_path = generate_pdf()
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF", f, file_name=os.path.basename(pdf_path))

    if st.button("Export Excel"):
        excel_path = export_excel()
        with open(excel_path, "rb") as f:
            st.download_button("Download Excel", f, file_name=os.path.basename(excel_path))

else:
    st.header("Dashboard")

    income_total = pd.read_sql(
        f"SELECT SUM(amount) total FROM income WHERE date BETWEEN '{start_date}' AND '{end_date}'",
        conn
    )["total"][0] or 0

    expense_total = pd.read_sql(
        f"SELECT SUM(amount) total FROM expenses WHERE date BETWEEN '{start_date}' AND '{end_date}'",
        conn
    )["total"][0] or 0

    savings_total = pd.read_sql(
        f"SELECT SUM(amount) total FROM savings WHERE date BETWEEN '{start_date}' AND '{end_date}'",
        conn
    )["total"][0] or 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Income", f"Rp {income_total:,.0f}")
    col2.metric("Expenses", f"Rp {expense_total:,.0f}")
    col3.metric("Savings", f"Rp {savings_total:,.0f}")

    chart = pd.read_sql(
        "SELECT contributor, SUM(amount) amount FROM income GROUP BY contributor",
        conn
    )
    st.bar_chart(chart.set_index("contributor"))
