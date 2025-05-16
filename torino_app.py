import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import rasterio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from folium.raster_layers import ImageOverlay
from folium import Choropleth
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
    "🗼️ Interactive Map", "📊 Data Exploration", "📈 Trends Over Time", "🏩 Urban SDG 11 Insights"])

# ── File mappings ────────────────────────────────────────────────────────────
DATA_DIR = "Torino"
GEOJSON = "torino_only.geojson"

FILE_MAP = {
    "NO2": "no2_turin_clipped.tif",
    "SO2": "so2_turin_clipped.tif",
    "CH4": "ch4_turin_clipped.tif",
    "O3":  "o3_turin_clipped.tif",
    "HCHO":"hcho_turin_clipped.tif"
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

# ── CSV path for Streamlit Cloud ───────────────────────────────────────────
DATA_PATH = ""

# ── Map Section ──────────────────────────────────────────────────────────────
if scroll_target == "🗼️ Interactive Map":
    center = regions.geometry.centroid.iloc[0].coords[0][::-1]
    m = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron")

    try:
        veh_mob = pd.read_csv(os.path.join(DATA_PATH, "torino_vehicle_mobility.csv"))
        socio = pd.read_csv(os.path.join(DATA_PATH, "torino_socio_econ_factors.csv"))
        pop = pd.read_csv(os.path.join(DATA_PATH, "Resident population.csv"))

        veh_mob.rename(columns={"municipality": "Municipality"}, inplace=True)
        socio.rename(columns={"municipality": "Municipality"}, inplace=True)
        pop["Municipality"] = "Torino"
        pop = pop.groupby("Municipality", as_index=False)["Total"].sum()

        overlay_data = regions_stats[["name", "geometry"]].rename(columns={"name": "Municipality"})
        overlay_data = overlay_data.merge(veh_mob, on="Municipality", how="left")
        overlay_data = overlay_data.merge(pop, on="Municipality", how="left")
        overlay_data = overlay_data.merge(socio, on="Municipality", how="left")

        # Pollution overlay
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

        # Choropleths
        Choropleth(
            geo_data=overlay_data,
            data=overlay_data,
            columns=["Municipality", "vehicle_per_1000"],
            key_on="feature.properties.Municipality",
            fill_color="YlGnBu",
            fill_opacity=0.6,
            line_opacity=0.2,
            name="🚗 Vehicle Density"
        ).add_to(m)

        Choropleth(
            geo_data=overlay_data,
            data=overlay_data,
            columns=["Municipality", "Total"],
            key_on="feature.properties.Municipality",
            fill_color="PuRd",
            fill_opacity=0.6,
            line_opacity=0.2,
            name="👥 Population"
        ).add_to(m)

        Choropleth(
            geo_data=overlay_data,
            data=overlay_data,
            columns=["Municipality", "housing_quality_index"],
            key_on="feature.properties.Municipality",
            fill_color="Greens",
            fill_opacity=0.6,
            line_opacity=0.2,
            name="🏠 Housing Quality"
        ).add_to(m)

        folium.GeoJson(
            overlay_data,
            name="Municipalities",
            style_function=lambda f: {"color": "black", "weight": 1, "fillOpacity": 0},
            tooltip=folium.GeoJsonTooltip(
                fields=["Municipality", "vehicle_per_1000", "Total", "housing_quality_index"],
                aliases=["Municipality", "Vehicles/1000", "Population", "Housing Quality"],
                localize=True,
                sticky=True
            )
        ).add_to(m)

        folium.LayerControl().add_to(m)

    except Exception as e:
        st.warning(f"Could not load socio-economic overlays: {e}")

    st.markdown("### 🗼️ Interactive Map")
    st_folium(m, width=1200, height=600)
    st.markdown("**🗱️ Darker colors indicate higher risk or density zones. Prioritize for urban interventions.**")
