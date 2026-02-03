import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, time
import calendar

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Couple Finance",
    layout="wide"
)

DB_PATH = "app.db"

# =========================
# DATABASE CONNECTION
# =========================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# =========================
# TABLE CREATION
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
    tanggal DATE,
    contributor TEXT,
    account TEXT,
    amount REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS itinerary (
    id INTEGER PRIMARY KEY,
    tanggal DATE,
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
# HELPERS
# =========================
def load_df(query):
    return pd.read_sql(query, conn)

def table_exists(name):
    q = f"""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='{name}'
    """
    return not load_df(q).empty

def safe_load_dates():
    dfs = []
    if table_exists("itinerary"):
        dfs.append(load_df("SELECT tanggal FROM itinerary"))
    if table_exists("income"):
        dfs.append(load_df("SELECT tanggal FROM income"))

    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        df["tanggal"] = pd.to_datetime(df["tanggal"])
        return df
    return pd.DataFrame(columns=["tanggal"])

def calc_duration(start, end):
    delta = datetime.combine(date.today(), end) - datetime.combine(date.today(), start)
    return max(int(delta.total_seconds() / 60), 0)

# =========================
# GLOBAL TIME FILTER
# =========================
st.sidebar.header("Filter Waktu")

dates_df = safe_load_dates()

if not dates_df.empty:
    years = sorted(dates_df["tanggal"].dt.year.unique())
else:
    years = [datetime.now().year]

year = st.sidebar.selectbox("Tahun", years)
month_name = st.sidebar.selectbox("Bulan", list(calendar.month_name)[1:])
month = list(calendar.month_name).index(month_name)

# =========================
# LOAD DATA
# =========================
category_df = load_df("SELECT * FROM expense_category")

itinerary_df = load_df(f"""
SELECT * FROM itinerary
WHERE strftime('%Y', tanggal)='{year}'
AND strftime('%m', tanggal)='{month:02d}'
""")

income_df = load_df(f"""
SELECT * FROM income
WHERE strftime('%Y', tanggal)='{year}'
AND strftime('%m', tanggal)='{month:02d}'
""")

# =========================
# DASHBOARD
# =========================
st.title("Couple Finance Dashboard")

total_income = income_df["amount"].sum() if not income_df.empty else 0
total_expense = itinerary_df["actual_budget"].sum() if not itinerary_df.empty else 0

c1, c2, c3 = st.columns(3)
c1.metric("Total Income", f"Rp {total_income:,.0f}")
c2.metric("Total Expense", f"Rp {total_expense:,.0f}")
c3.metric("Balance", f"Rp {total_income - total_expense:,.0f}")

st.divider()

# =========================
# EXPENSE PROGRESS
# =========================
st.subheader("Budget Progress")

if not category_df.empty:
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
else:
    st.info("Belum ada kategori expenses")

# =========================
# ITINERARY BY DATE
# =========================
st.divider()
st.header("Itinerary Planner")

selected_date = st.date_input("Pilih Tanggal")

daily_df = itinerary_df[
    itinerary_df["tanggal"] == str(selected_date)
]

if not daily_df.empty:
    st.subheader("Agenda Hari Ini")
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
        category_df["name"].tolist() if not category_df.empty else []
    )

    planned_budget = 0
    if not category_df.empty and category:
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
            selected_date,
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

export = {
    "Itinerary": itinerary_df,
    "Income": income_df,
    "Expense Category": category_df
}

with pd.ExcelWriter("export.xlsx", engine="xlsxwriter") as writer:
    for k, v in export.items():
        v.to_excel(writer, sheet_name=k, index=False)

with open("export.xlsx", "rb") as f:
    st.download_button(
        "Download Excel",
        f,
        file_name="couple_finance.xlsx"
    )
