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
    "🗼️ Interactive Map", "📊 Data Exploration", "📈 Trends Over Time", "🏩 Urban SDG 11 Insights", "📃 Socio-Economic Analysis"])

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

center = regions.geometry.centroid.iloc[0].coords[0][::-1]

# ── Map Section ──────────────────────────────────────────────────────────────
if scroll_target == "🗼️ Interactive Map":
    m = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron")

    folium.GeoJson(
        regions,
        name="Municipalities",
        style_function=lambda f: {"color": "black", "weight": 1, "fillOpacity": 0},
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Municipality"], sticky=True)
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

# ── Socio-Economic Analysis ────────────────────────────────────────────────
if scroll_target == "📃 Socio-Economic Analysis":
    st.markdown("## 📃 Socio-Economic Analysis")
    try:
        veh_mob = pd.read_csv("torino_vehicle_mobility.csv")
        socio = pd.read_csv("torino_socio_econ_factors.csv")
        pop = pd.read_csv("Resident population.csv")

        veh_mob["municipality"] = veh_mob["municipality"].str.lower().str.strip()
        socio["municipality"] = socio["municipality"].str.lower().str.strip()
        pop["Municipality"] = pop["Municipality"].str.lower().str.strip()

        stats_df = regions_stats.copy()
        stats_df["name"] = stats_df["name"].str.lower().str.strip()

        pop = pop.groupby("Municipality", as_index=False)["Total"].sum()

        merged = stats_df[["name", "mean", "geometry"]].rename(columns={"name": "Municipality", "mean": f"{pollutant}_Level"})
        merged = merged.merge(veh_mob, left_on="Municipality", right_on="municipality", how="left")
        merged = merged.merge(socio, left_on="Municipality", right_on="municipality", how="left")
        merged = merged.merge(pop, on="Municipality", how="left")
        merged = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")

        try:
            m2 = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron")
            geojson = folium.GeoJson(
                merged,
                tooltip=folium.GeoJsonTooltip(
                    fields=["Municipality", f"{pollutant}_Level", "vehicle_per_1000", "housing_quality_index", "Total"],
                    aliases=["Municipality", "Pollution", "Vehicles/1000", "Housing Quality", "Population"]
                )
            )
            geojson.add_to(m2)
            st.markdown("### 🌐 Socio-Economic Map View")
            st_folium(m2, width=1200, height=500)
        except Exception as map_error:
            st.warning(f"Map not shown: {map_error}")

        st.markdown("### 🔍 Integrated Insights")
        st.markdown("- *High vehicle density* often correlates with higher NO₂.")
        st.markdown("- *Lower housing quality* = poorer planning & higher exposure.")
        st.markdown("- *Population density* is tied to urban heat and traffic.")

        st.markdown("### 🏆 Top Municipalities by Pollution & Risk Factors")
        st.dataframe(merged[["Municipality", f"{pollutant}_Level", "vehicle_per_1000", "housing_quality_index", "Total"]]
                     .sort_values(by=f"{pollutant}_Level", ascending=False).head(10))

        st.markdown("### 📈 Correlation Matrix")
        corr = merged.select_dtypes(include=np.number).corr()
        fig_corr, ax_corr = plt.subplots(figsize=(10, 6))
        sns.heatmap(corr, annot=True, cmap="coolwarm", ax=ax_corr)
        st.pyplot(fig_corr)

        st.markdown("### 🚨 Auto-Highlighted Risk Zones")
        top_risk = merged.sort_values(by=f"{pollutant}_Level", ascending=False).head(5)
        st.dataframe(top_risk[["Municipality", f"{pollutant}_Level", "vehicle_per_1000", "housing_quality_index", "Total"]]
                     .rename(columns={f"{pollutant}_Level": "Pollution Level"}))

        st.markdown("### 🧶 SDG 11 Compliance Score")
        def compute_sdg_score(row):
            pollution_score = 1 - min(row[f"{pollutant}_Level"] / vmax, 1)
            vehicle_score = 1 - min(row["vehicle_per_1000"] / 1000, 1)
            housing_score = row["housing_quality_index"] / 100 if pd.notnull(row["housing_quality_index"]) else 0
            return round((pollution_score + vehicle_score + housing_score) / 3 * 100, 2)

        merged["SDG_11_Score"] = merged.apply(compute_sdg_score, axis=1)

        fig_score, ax_score = plt.subplots(figsize=(10, 5))
        top_score = merged.sort_values("SDG_11_Score", ascending=False).head(10)
        sns.barplot(x="SDG_11_Score", y="Municipality", data=top_score, palette="Greens", ax=ax_score)
        ax_score.set_title("Top 10 Municipalities by SDG 11 Compliance Score")
        st.pyplot(fig_score)

        st.markdown("\u2139 SDG 11 Score = Pollution + Vehicle + Housing Index → Higher is better.")

    except Exception as e:
        st.error(f"Error loading socio-economic data: {e}")
