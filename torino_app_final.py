# ── Socio-Economic Analysis ────────────────────────────────────────────────
if scroll_target == "📃 Socio-Economic Analysis":
    st.markdown("## 📃 Socio-Economic Analysis")
    try:
        # Load datasets
        veh_mob = pd.read_csv("torino_vehicle_mobility.csv")
        socio = pd.read_csv("torino_socio_econ_factors.csv")
        pop = pd.read_csv("Resident population.csv")

        # Clean string formats for merge
        veh_mob["municipality"] = veh_mob["municipality"].str.lower().str.strip()
        socio["municipality"] = socio["municipality"].str.lower().str.strip()
        pop["Municipality"] = pop["Municipality"].str.lower().str.strip()
        stats_df = regions_stats.copy()
        stats_df["name"] = stats_df["name"].str.lower().str.strip()

        # Merge
        pop = pop.groupby("Municipality", as_index=False)["Total"].sum()
        merged = stats_df[["name", "mean", "geometry"]].rename(columns={"name": "Municipality", "mean": f"{pollutant}_Level"})
        merged = merged.merge(veh_mob, left_on="Municipality", right_on="municipality", how="left")
        merged = merged.merge(socio, left_on="Municipality", right_on="municipality", how="left")
        merged = merged.merge(pop, on="Municipality", how="left")
        merged = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")

        # Try to show the map (fallback if error)
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
            st.markdown("### 🌐 Socio-Economic Interactive Map")
            st_folium(m2, width=1200, height=500)
        except Exception as map_err:
            st.warning(f"⚠️ Map not displayed: {map_err}")
            st.info("Continuing with SDG analysis below...")

        # Compute SDG 11 Score
        def compute_sdg_score(row):
            pollution_score = 1 - min(row[f"{pollutant}_Level"] / vmax, 1)
            vehicle_score = 1 - min(row["vehicle_per_1000"] / 1000, 1)
            housing_score = row["housing_quality_index"] / 100 if pd.notnull(row["housing_quality_index"]) else 0
            return round((pollution_score + vehicle_score + housing_score) / 3 * 100, 2)

        merged["SDG_11_Score"] = merged.apply(compute_sdg_score, axis=1)

        # SDG Table
        st.markdown("### 📊 SDG Summary & Insights")
        st.dataframe(
            merged[["Municipality", f"{pollutant}_Level", "vehicle_per_1000", "housing_quality_index", "Total", "SDG_11_Score"]]
            .sort_values("SDG_11_Score", ascending=False)
        )

        # Top 5 At-Risk
        st.markdown("### 🚨 Top 5 At-Risk Municipalities")
        st.table(
            merged[["Municipality", "SDG_11_Score"]]
            .sort_values("SDG_11_Score", ascending=True)
            .head(5)
            .reset_index(drop=True)
        )

        # Download CSV
        csv = merged.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Full Dataset (CSV)",
            data=csv,
            file_name="torino_sdg11_socio.csv",
            mime="text/csv"
        )

        # Bar Chart
        st.markdown("### 📉 SDG 11 Score Distribution")
        fig, ax = plt.subplots(figsize=(10, 4))
        sorted_df = merged.sort_values("SDG_11_Score", ascending=True)
        sns.barplot(x="SDG_11_Score", y="Municipality", data=sorted_df, palette="coolwarm", ax=ax)
        ax.set_title("SDG 11 Score by Municipality")
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Error loading socio-economic data: {e}")
