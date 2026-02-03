import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, time
import calendar

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Couple Finance", layout="wide")

DB_PATH = "app.db"

# =========================
# DB CONNECTION
# =========================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# =========================
# CREATE TABLES
# =========================
cur.execute("""
CREATE TABLE IF NOT EXISTS expense_category (
    id INTEGER PRIMARY KEY,
    name TEXT,
    monthly_budget REAL
)
""")

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
CREATE TABLE IF NOT EXISTS itinerary (
    id INTEGER PRIMARY KEY,
    tanggal TEXT,
    activity TEXT,
    place TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_minutes INTEGER,
    category TEXT,
    planned_budget REAL,
    actual_budget REAL
)
""")

conn.commit()

# =========================
# SAFE LOAD FUNCTION
# =========================
def safe_read_sql(query, columns):
    try:
        df = pd.read_sql(query, conn)
    except Exception:
        df = pd.DataFrame(columns=columns)

    # FORCE SCHEMA
    for col in columns:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")

    return df[columns]

# =========================
# HELPERS
# =========================
def calc_duration(start, end):
    delta = datetime.combine(date.today(), end) - datetime.combine(date.today(), start)
    return max(int(delta.total_seconds() / 60), 0)

# =========================
# LOAD DATA (SCHEMA SAFE)
# =========================
category_df = safe_read_sql(
    "SELECT * FROM expense_category",
    ["id", "name", "monthly_budget"]
)

income_df_all = safe_read_sql(
    "SELECT * FROM income",
    ["id", "tanggal", "contributor", "account", "amount"]
)

itinerary_df_all = safe_read_sql(
    "SELECT * FROM itinerary",
    [
        "id", "tanggal", "activity", "place",
        "start_time", "end_time", "duration_minutes",
        "category", "planned_budget", "actual_budget"
    ]
)

# =========================
# PARSE DATE SAFELY
# =========================
income_df_all["tanggal"] = pd.to_datetime(
    income_df_all["tanggal"], errors="coerce"
)
itinerary_df_all["tanggal"] = pd.to_datetime(
    itinerary_df_all["tanggal"], errors="coerce"
)

# =========================
# GLOBAL FILTER
# =========================
st.sidebar.header("Filter Waktu")

all_dates = pd.concat(
    [
        income_df_all[["tanggal"]],
        itinerary_df_all[["tanggal"]]
    ],
    ignore_index=True
).dropna()

if not all_dates.empty:
    years = sorted(all_dates["tanggal"].dt.year.unique())
else:
    years = [datetime.now().year]

year = st.sidebar.selectbox("Tahun", years)
month_name = st.sidebar.selectbox("Bulan", list(calendar.month_name)[1:])
month = list(calendar.month_name).index(month_name)

# =========================
# FILTER DATA
# =========================
income_df = income_df_all[
    (income_df_all["tanggal"].dt.year == year) &
    (income_df_all["tanggal"].dt.month == month)
]

itinerary_df = itinerary_df_all[
    (itinerary_df_all["tanggal"].dt.year == year) &
    (itinerary_df_all["tanggal"].dt.month == month)
]

# =========================
# DASHBOARD
# =========================
st.title("Couple Finance Dashboard")

total_income = income_df["amount"].sum()
total_expense = itinerary_df["actual_budget"].sum()

c1, c2, c3 = st.columns(3)
c1.metric("Total Income", f"Rp {total_income:,.0f}")
c2.metric("Total Expense", f"Rp {total_expense:,.0f}")
c3.metric("Balance", f"Rp {total_income - total_expense:,.0f}")

st.divider()

# =========================
# EXPENSE PROGRESS
# =========================
st.subheader("Budget Progress")

if category_df.empty:
    st.info("Belum ada kategori expenses")
else:
    for _, row in category_df.iterrows():
        actual = itinerary_df[
            itinerary_df["category"] == row["name"]
        ]["actual_budget"].sum()

        planned = row["monthly_budget"]
        progress = min(actual / planned, 1) if planned > 0 else 0

        st.write(row["name"])
        st.progress(progress)
        st.caption(
            f"Planned: Rp {planned:,.0f} | Actual: Rp {actual:,.0f}"
        )

# =========================
# ITINERARY PLANNER
# =========================
st.divider()
st.header("Itinerary Planner")

selected_date = st.date_input("Pilih Tanggal")

daily_df = itinerary_df_all[
    itinerary_df_all["tanggal"] == pd.to_datetime(selected_date)
]

if not daily_df.empty:
    st.dataframe(
        daily_df[
            [
                "activity", "place", "start_time", "end_time",
                "duration_minutes", "category",
                "planned_budget", "actual_budget"
            ]
        ],
        use_container_width=True
    )
else:
    st.info("Belum ada itinerary di tanggal ini")

# =========================
# ADD ITINERARY
# =========================
st.subheader("Tambah Kegiatan")

with st.form("add_itinerary"):
    c1, c2 = st.columns(2)
    activity = c1.text_input("Nama Kegiatan")
    place = c2.text_input("Tempat")

    c3, c4 = st.columns(2)
    start = c3.time_input("Mulai", time(9, 0))
    end = c4.time_input("Selesai", time(10, 0))

    duration = calc_duration(start, end)

    category = st.selectbox(
        "Expense Category",
        category_df["name"].tolist()
    )

    planned_budget = category_df[
        category_df["name"] == category
    ]["monthly_budget"].values[0]

    actual_budget = st.number_input("Budget Aktual", min_value=0.0)

    st.caption(f"Estimasi Waktu: {duration} menit")
    st.caption(f"Estimasi Budget (Planned): Rp {planned_budget:,.0f}")

    if st.form_submit_button("Simpan Itinerary"):
        cur.execute("""
        INSERT INTO itinerary VALUES (
            NULL,?,?,?,?,?,?,?,?,?
        )
        """, (
            str(selected_date),
            activity,
            place,
            start.strftime("%H:%M"),
            end.strftime("%H:%M"),
            duration,
            category,
            planned_budget,
            actual_budget
        ))
        conn.commit()
        st.success("Itinerary berhasil ditambahkan")

# =========================
# EXPORT
# =========================
st.divider()
st.header("Export")

with pd.ExcelWriter("export.xlsx", engine="xlsxwriter") as writer:
    itinerary_df.to_excel(writer, sheet_name="Itinerary", index=False)
    income_df.to_excel(writer, sheet_name="Income", index=False)
    category_df.to_excel(writer, sheet_name="Expense Category", index=False)

with open("export.xlsx", "rb") as f:
    st.download_button("Download Excel", f, file_name="couple_finance.xlsx")
