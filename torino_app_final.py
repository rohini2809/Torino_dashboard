import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import rasterio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from folium.raster_layers import ImageOverlay
from folium import Choropleth, GeoJsonTooltip
from PIL import Image
import os
import io
import seaborn as sns
from rasterstats import zonal_stats
import tempfile
import pandas as pd

# ── Page setup ─────────────────────────────────────────────────────────────
st.set_page_config(layout="wide")
st.title("🌍 Air Pollution in Turin - SDG 11 Dashboard")
st.markdown("""
This dashboard explores satellite-based pollution data for **Turin, Italy** in support of **SDG 11: Sustainable Cities and Communities**. 
Scroll or click a section to navigate.
""")

st.sidebar.title("📌 Navigation")
scroll_target = st.sidebar.radio("Jump to Section:", [
    "🗼️ Interactive Map", "📊 Data Exploration", "📈 Trends Over Time", "🏩 Urban SDG 11 Insights", "📃 Socio-Economic Analysis"])

# ── File mappings ────────────────────────────────────────────────────────────
DATA_DIR = "Torino"
GEOJSON = "torino_only.geojson"
FILE_MAP = {
    "NO2": "no2_turin_clipped.tif",
    "SO2": "so2_turin_clipped.tif",
    "CH4": "ch4_turin_clipped.tif",
    "O3":  "o3_turin_clipped.tif",
    "HCHO": "hcho_turin_clipped.tif"
}

pollutant = st.sidebar.selectbox("Select pollutant:", list(FILE_MAP.keys()))
tif_path = os.path.join(DATA_DIR, FILE_MAP[pollutant])

# ── Load boundary GeoJSON and raster ─────────────────────────────────────────
regions = gpd.read_file(GEOJSON)
if regions.crs is None:
    regions.set_crs(epsg=4326, inplace=True)

with rasterio.open(tif_path) as src:
    arr = src.read(1)
    arr[arr == src.nodata] = np.nan
    bounds = src.bounds
    vmin, vmax = np.nanmin(arr), np.nanmax(arr)
    meanv = np.nanmean(arr)
    norm = (arr - vmin) / (vmax - vmin)
    norm = np.nan_to_num(norm)
    stats = zonal_stats(regions, tif_path, stats=["mean"], geojson_out=True, nodata=src.nodata)
    regions_stats = gpd.GeoDataFrame.from_features(stats)
    regions_stats.set_crs(epsg=4326, inplace=True)

# ── Interactive Map ──────────────────────────────────────────────────────────
if scroll_target == "🗼️ Interactive Map":
    center = regions.geometry.centroid.iloc[0].coords[0][::-1]
    m = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron")

    folium.GeoJson(
        regions,
        name="Municipalities",
        style_function=lambda f: {"color": "black", "weight": 1, "fillOpacity": 0},
        tooltip=GeoJsonTooltip(fields=["name"], aliases=["Municipality"])
    ).add_to(m)

    cmap = cm.get_cmap("plasma")
    rgba = (cmap(norm)[:, :, :3] * 255).astype(np.uint8)
    img = Image.fromarray(rgba)
    t = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(t.name)
    ImageOverlay(
        image=t.name,
        bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
        opacity=0.6,
        name="Pixel Heatmap"
    ).add_to(m)

    Choropleth(
        geo_data=regions_stats,
        data=regions_stats,
        columns=["name", "mean"],
        key_on="feature.properties.name",
        fill_color="YlOrRd",
        fill_opacity=0.5,
        line_opacity=0.2,
        legend_name=f"{pollutant} Mean by Municipality"
    ).add_to(m)

    folium.LayerControl().add_to(m)
    st.markdown("### 🗼️ Interactive Map")
    st_folium(m, width=1200, height=600)
    st.markdown("**🗱️ Darker colors indicate higher risk zones. Prioritize these areas for urban planning actions.**")

# ── Data Exploration ─────────────────────────────────────────────────────────
if scroll_target == "📊 Data Exploration":
    st.markdown("## 📊 Data Exploration")
    st.markdown("#### 🔢 Pixel Grid Heatmap (Preview)")
    fig1, ax1 = plt.subplots(figsize=(6, 5))
    sns.heatmap(norm[::10, ::10], cmap="plasma", cbar=True, ax=ax1)
    st.pyplot(fig1)

    st.markdown("#### 📈 Pollution Value Distribution")
    fig2, ax2 = plt.subplots(figsize=(6, 3))
    vals = norm.flatten()
    vals = vals[vals > 0]
    ax2.hist(vals, bins=30, color="orange", edgecolor="black")
    ax2.set_xlabel("Normalized Value")
    ax2.set_ylabel("Pixel Count")
    st.pyplot(fig2)

    st.markdown("#### 🏙️ Municipality Pollution Ranking")
    df_table = regions_stats[["name", "mean"]].sort_values(by="mean", ascending=False)
    st.dataframe(df_table.rename(columns={"name": "Municipality", "mean": f"{pollutant} Level"}))

# ── Trends ───────────────────────────────────────────────────────────────────
if scroll_target == "📈 Trends Over Time":
    st.markdown("## 📈 Urban Pollution Trends (CO & Aerosol Index)")
    try:
        co_df = pd.read_csv("Sentinel-5P CO-CO_VISUALIZED-2020-05-13T00_00_00.000Z-2025-05-13T23_59_59.999Z.csv")
        aer_df = pd.read_csv("Sentinel-5P AER_AI-AER_AI_340_AND_380_VISUALIZED-2019-06-14T00_00_00.000Z-2024-06-14T23_59_59.999Z.csv")

        co_df["C0/date"] = pd.to_datetime(co_df["C0/date"])
        aer_df["C0/date"] = pd.to_datetime(aer_df["C0/date"])

        co_df.rename(columns={"C0/date": "Date", "C0/mean": "CO_Level"}, inplace=True)
        aer_df.rename(columns={"C0/date": "Date", "C0/mean": "Aerosol_Index"}, inplace=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🟠 Carbon Monoxide (CO)")
            fig_co, ax_co = plt.subplots(figsize=(6, 3))
            ax_co.plot(co_df["Date"], co_df["CO_Level"], color="orange")
            ax_co.set_ylabel("CO Level")
            ax_co.set_xlabel("Date")
            st.pyplot(fig_co)
        with col2:
            st.markdown("#### 🔵 Aerosol Index")
            fig_ai, ax_ai = plt.subplots(figsize=(6, 3))
            ax_ai.plot(aer_df["Date"], aer_df["Aerosol_Index"], color="blue")
            ax_ai.set_ylabel("Aerosol Index")
            ax_ai.set_xlabel("Date")
            st.pyplot(fig_ai)

    except Exception as e:
        st.warning(f"Could not load trends data: {e}")

# ── SDG 11 Insight ───────────────────────────────────────────────────────────
if scroll_target == "🏩 Urban SDG 11 Insights":
    st.markdown("## 🏩 Urban SDG 11 Insights")
    st.markdown("### 📌 Priority Planning Actions")
    st.success("1. High-risk zones from NO2 map should be targeted with traffic and emissions policy.")
    st.info("2. Trends show seasonal variation — plan interventions during high exposure months.")
    st.warning("3. Use zoning laws to restrict industrial emissions in urban cores.")
