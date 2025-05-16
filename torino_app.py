...
        st.markdown("### 🚨 Auto-Highlighted Risk Zones")
        top_risk = merged.sort_values(by=f"{pollutant}_Level", ascending=False).head(5)
        st.dataframe(top_risk[["Municipality", f"{pollutant}_Level", "vehicle_per_1000", "housing_quality_index", "Total"]]
                     .rename(columns={f"{pollutant}_Level": "Pollution Level"}))

        st.markdown("### 🧮 SDG 11 Compliance Score")
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

        st.markdown("**ℹ️ SDG 11 Score is computed using pollution, vehicle density, and housing quality. A higher score indicates better alignment with sustainable urban goals.**")
