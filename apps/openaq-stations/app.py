import os
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

st.set_page_config(page_title="OpenAQ India Stations", layout="wide")

# ---- 1. Config: read from app.yaml, stop early if missing ----
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID")
STATION_TABLE = os.getenv("STATION_TABLE")

if not WAREHOUSE_ID or not STATION_TABLE:
    st.error("Missing WAREHOUSE_ID or STATION_TABLE. Check app resources and app.yaml keys.")
    st.stop()

cfg = Config()

# ---- 2. Data: one query, cached ----
@st.cache_data(ttl=600)
def load_stations():
    with sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {STATION_TABLE}")
            return cur.fetchall_arrow().to_pandas()

try:
    df = load_stations()
except Exception as e:
    st.error(f"Could not load data: {e}")
    st.stop()

# ---- 3. Filters (left sidebar) ----
st.title("OpenAQ India — Station Explorer")

def pollutant_list(text):
    return [p.strip() for p in (text or "").split(",") if p.strip()]

all_pollutants = sorted({p for text in df["pollutants"] for p in pollutant_list(text)})
pollutant = st.sidebar.selectbox("Pollutant", ["All"] + all_pollutants)
providers = st.sidebar.multiselect("Provider", sorted(df["provider_name"].dropna().unique()))
active_only = st.sidebar.checkbox("Active stations only", value=True)

view = df
if pollutant != "All":
    view = view[view["pollutants"].apply(lambda t: pollutant in pollutant_list(t))]
if providers:
    view = view[view["provider_name"].isin(providers)]
if active_only:
    view = view[view["is_active"] == True]

# ---- 4. Output: numbers, map, table ----
c1, c2, c3 = st.columns(3)
c1.metric("Stations shown", len(view))
c2.metric("Active (all India)", int((df["is_active"] == True).sum()))
c3.metric("Total stations", len(df))

st.map(view[["latitude", "longitude"]].dropna())

st.dataframe(
    view[["location_name", "provider_name", "pollutants", "sensor_count", "is_active", "last_seen_utc"]],
    hide_index=True,
)