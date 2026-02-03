import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, time
import calendar

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="💖 Couple Finance",
    page_icon="💸",
    layout="wide"
)

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("app.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY,
    tanggal TEXT,
    contributor TEXT,
    account TEXT,
    amount REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS expense_category (
    id INTEGER PRIMARY KEY,
    name TEXT,
    monthly_budget REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS itinerary (
    id INTEGER PRIMARY KEY,
    tanggal TEXT,
    activity TEXT,
    place TEXT,
    start_time TEXT,
    end_time TEXT,
    duration INTEGER,
    category TEXT,
    planned_budget REAL,
    actual_budget REAL
)
""")

conn.commit()

# =========================
# HELPERS
# =========================
def load_df(query, cols):
    try:
        df = pd.read_sql(query, conn)
    except:
        df = pd.DataFrame(columns=cols)

    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def calc_duration(start, end):
    delta = datetime.combine(date.today(), end) - datetime.combine(date.today(), start)
    return max(int(delta.total_seconds() / 60), 0)

# =========================
# LOAD DATA
# =========================
income_df = load_df(
    "SELECT * FROM income",
    ["id", "tanggal", "contributor", "account", "amount"]
)
expense_df = load_df(
    "SELECT * FROM expense_category",
    ["id", "name", "monthly_budget"]
)
itinerary_df = load_df(
    "SELECT * FROM itinerary",
    ["id","tanggal","activity","place","start_time","end_time","duration","category","planned_budget","actual_budget"]
)

income_df["tanggal"] = pd.to_datetime(income_df["tanggal"], errors="coerce")
itinerary_df["tanggal"] = pd.to_datetime(itinerary_df["tanggal"], errors="coerce")

# =========================
# SIDEBAR MENU
# =========================
st.sidebar.title("💖 Couple Finance")
menu = st.sidebar.radio(
    "Menu",
    ["🏠 Dashboard", "💰 Income", "📦 Expenses", "🗺️ Itinerary"]
)

# =========================
# DASHBOARD
# =========================
if menu == "🏠 Dashboard":
    st.title("🏠 Dashboard Bulanan")

    col1, col2 = st.columns(2)
    year = col1.selectbox("Tahun", sorted(income_df["tanggal"].dt.year.dropna().unique()) or [datetime.now().year])
    month_name = col2.selectbox("Bulan", list(calendar.month_name)[1:])
    month = list(calendar.month_name).index(month_name)

    inc = income_df[
        (income_df["tanggal"].dt.year == year) &
        (income_df["tanggal"].dt.month == month)
    ]

    iti = itinerary_df[
        (itinerary_df["tanggal"].dt.year == year) &
        (itinerary_df["tanggal"].dt.month == month)
    ]

    total_income = inc["amount"].sum()
    total_expense = iti["actual_budget"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total Income", f"Rp {total_income:,.0f}")
    c2.metric("💸 Total Expense", f"Rp {total_expense:,.0f}")
    c3.metric("💖 Balance", f"Rp {total_income-total_expense:,.0f}")

    st.divider()
    st.subheader("📊 Progress Budget")

    if expense_df.empty:
        st.info("Belum ada kategori expense")
    else:
        for _, row in expense_df.iterrows():
            actual = iti[iti["category"] == row["name"]]["actual_budget"].sum()
            planned = row["monthly_budget"]
            ratio = min(actual / planned, 1) if planned > 0 else 0

            st.write(f"**{row['name']}**")
            st.progress(ratio)
            st.caption(f"Planned: Rp {planned:,.0f} | Actual: Rp {actual:,.0f}")

# =========================
# INCOME
# =========================
elif menu == "💰 Income":
    st.title("💰 Income Tracker")

    with st.form("add_income"):
        c1, c2 = st.columns(2)
        tanggal = c1.date_input("Tanggal")
        contributor = c2.text_input("Contributor")

        c3, c4 = st.columns(2)
        account = c3.text_input("Account")
        amount = c4.number_input("Amount", min_value=0.0)

        if st.form_submit_button("Tambah Income"):
            cur.execute(
                "INSERT INTO income VALUES (NULL,?,?,?,?)",
                (str(tanggal), contributor, account, amount)
            )
            conn.commit()
            st.success("Income berhasil ditambahkan 💸")

    st.divider()
    st.subheader("📄 Riwayat Income")
    st.dataframe(income_df.sort_values("tanggal", ascending=False), use_container_width=True)

# =========================
# EXPENSES
# =========================
elif menu == "📦 Expenses":
    st.title("📦 Expense Categories")

    with st.form("add_expense"):
        name = st.text_input("Nama Kategori")
        budget = st.number_input("Monthly Budget", min_value=0.0)

        if st.form_submit_button("Tambah Kategori"):
            cur.execute(
                "INSERT INTO expense_category VALUES (NULL,?,?)",
                (name, budget)
            )
            conn.commit()
            st.success("Kategori berhasil ditambahkan 🎯")

    st.divider()
    st.dataframe(expense_df, use_container_width=True)

# =========================
# ITINERARY
# =========================
elif menu == "🗺️ Itinerary":
    st.title("🗺️ Itinerary Planner")

    selected_date = st.date_input("📅 Pilih Tanggal")

    daily = itinerary_df[itinerary_df["tanggal"] == pd.to_datetime(selected_date)]

    if daily.empty:
        st.info("Belum ada itinerary hari ini")
    else:
        st.dataframe(
            daily[
                ["activity","place","start_time","end_time","duration","category","planned_budget","actual_budget"]
            ],
            use_container_width=True
        )

    st.divider()
    st.subheader("➕ Tambah Kegiatan")

    with st.form("add_itinerary"):
        c1, c2 = st.columns(2)
        activity = c1.text_input("Nama Kegiatan")
        place = c2.text_input("Tempat")

        c3, c4 = st.columns(2)
        start = c3.time_input("Mulai", time(9,0))
        end = c4.time_input("Selesai", time(10,0))

        duration = calc_duration(start, end)

        category = st.selectbox("Kategori Expense", expense_df["name"].tolist())
        planned = expense_df[expense_df["name"] == category]["monthly_budget"].values[0] if not expense_df.empty else 0
        actual = st.number_input("Budget Aktual", min_value=0.0)

        st.caption(f"⏱️ Durasi: {duration} menit")
        st.caption(f"💰 Estimasi Budget: Rp {planned:,.0f}")

        if st.form_submit_button("Simpan Itinerary"):
            cur.execute("""
            INSERT INTO itinerary VALUES (NULL,?,?,?,?,?,?,?,?,?)
            """, (
                str(selected_date), activity, place,
                start.strftime("%H:%M"), end.strftime("%H:%M"),
                duration, category, planned, actual
            ))
            conn.commit()
            st.success("Itinerary berhasil ditambahkan 🥰")
