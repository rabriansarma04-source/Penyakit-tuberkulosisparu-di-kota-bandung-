import streamlit as st
import pandas as pd
import folium
import json
import re

from streamlit_folium import st_folium
import plotly.express as px

st.set_page_config(
    page_title="Dashboard TB Paru Kota Bandung",
    page_icon="🫁",
    layout="wide"
)

st.title("🫁 Dashboard Pemetaan dan Analisis Spasial")
st.subheader("Sebaran Kasus Tuberkulosis (TB) Paru Kota Bandung")
st.caption(
    "Catatan: jika satu kecamatan memiliki lebih dari satu baris data pada "
    "tahun yang sama di file sumber, jumlah kasus dihitung sebagai total "
    "agregat dari seluruh baris tersebut."
)
st.markdown("---")

EXCEL_PATH = "data/TB_PARU.xlsx"
GEOJSON_PATH = "assets/3273-kota-bandung-level-kecamatan.json"


def normalize_nama(nama):
    """Samakan format nama kecamatan (hilangkan spasi, jadikan huruf besar)
    agar data Excel & GeoJSON bisa dicocokkan walau penulisannya sedikit
    berbeda (contoh: 'UJUNG BERUNG' vs 'Ujungberung')."""
    return re.sub(r"\s+", "", str(nama)).strip().upper()


@st.cache_data
def load_data():
    df = pd.read_excel(EXCEL_PATH)
    # Kolom ke-2 pada file sumber kosong (header ganda "Kecamatan"), buang.
    df.columns = ["kota", "_kolom_kosong", "kecamatan", "jumlah_kasus", "satuan", "tahun"]
    df = df.drop(columns=["_kolom_kosong"])
    df["kecamatan"] = df["kecamatan"].astype(str).str.strip()
    return df


@st.cache_data
def load_geojson():
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


df_raw = load_data()
geojson_data = load_geojson()

# Bangun pemetaan nama kecamatan Excel -> nama resmi di GeoJSON
geo_name_map = {}
for feature in geojson_data["features"]:
    nama_resmi = str(feature["properties"]["nama_kecamatan"]).strip()
    feature["properties"]["district"] = nama_resmi
    geo_name_map[normalize_nama(nama_resmi)] = nama_resmi

df_raw["kecamatan"] = (
    df_raw["kecamatan"]
    .apply(normalize_nama)
    .map(geo_name_map)
    .fillna(df_raw["kecamatan"].str.title())
)

# Total kasus per kecamatan per tahun (menjumlahkan semua baris terkait)
df = (
    df_raw.groupby(["tahun", "kecamatan"], as_index=False)["jumlah_kasus"]
    .sum()
)

tahun_list = sorted(df["tahun"].unique())

selected_year = st.selectbox(
    "Pilih Tahun",
    tahun_list,
    index=len(tahun_list) - 1
)

df_year = df[df["tahun"] == selected_year].copy()

total_kecamatan_geo = len(geojson_data["features"])

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Kasus TB Paru", int(df_year["jumlah_kasus"].sum()))

with col2:
    st.metric("Kecamatan Tercatat", f"{len(df_year)} / {total_kecamatan_geo}")

with col3:
    st.metric("Kasus Tertinggi", int(df_year["jumlah_kasus"].max()))

with col4:
    kec_tertinggi = df_year.loc[df_year["jumlah_kasus"].idxmax(), "kecamatan"]
    st.metric("Kecamatan Tertinggi", kec_tertinggi)

st.markdown("---")

kasus_dict = dict(zip(df_year["kecamatan"], df_year["jumlah_kasus"]))

for feature in geojson_data["features"]:
    nama_kec = feature["properties"]["district"]
    feature["properties"]["jumlah_kasus"] = int(kasus_dict.get(nama_kec, 0))

col_kiri, col_kanan = st.columns([1.5, 1])

with col_kiri:
    st.subheader("🗺️ Peta Sebaran TB Paru per Kecamatan")
    st.caption("💡 Hover untuk info, klik untuk detail")

    m = folium.Map(
        location=[-6.9175, 107.6191],
        zoom_start=12,
        tiles="CartoDB positron"
    )

    folium.Choropleth(
        geo_data=geojson_data,
        data=df_year,
        columns=["kecamatan", "jumlah_kasus"],
        key_on="feature.properties.district",
        fill_color="YlOrRd",
        fill_opacity=0.8,
        line_opacity=0.8,
        line_color="black",
        legend_name=f"Jumlah Kasus TB Paru {selected_year}",
        nan_fill_color="lightgray",
        highlight=True
    ).add_to(m)

    folium.GeoJson(
        geojson_data,
        style_function=lambda x: {
            "fillOpacity": 0,
            "weight": 1.5,
            "color": "#333333"
        },
        highlight_function=lambda x: {
            "fillOpacity": 0.25,
            "weight": 3,
            "color": "#FF4444"
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["district", "jumlah_kasus"],
            aliases=["Kecamatan:", "Jumlah Kasus:"],
            sticky=True
        ),
        popup=folium.GeoJsonPopup(
            fields=["district", "jumlah_kasus"],
            aliases=["📍 Kecamatan", f"🦠 Kasus TB Paru {selected_year}"],
            localize=True,
            labels=True,
            style=(
                "background-color: white;"
                "color: #333333;"
                "font-family: Arial;"
                "font-size: 14px;"
                "padding: 10px;"
                "border-radius: 6px;"
                "border: 1px solid #cccccc;"
            )
        )
    ).add_to(m)

    map_data = st_folium(
        m,
        width=900,
        height=550,
        returned_objects=["last_object_clicked_popup"]
    )

    jumlah_max = int(df_year["jumlah_kasus"].max())
    q1 = int(df_year["jumlah_kasus"].quantile(0.25))
    q2 = int(df_year["jumlah_kasus"].quantile(0.50))
    q3 = int(df_year["jumlah_kasus"].quantile(0.75))

    st.markdown(
        f"""
        <div style="font-size:13px; margin-top:8px; line-height:1.8;">
            <b>Informasi:</b><br>
            🟡 <b>Kuning</b> — Kasus rendah (1 – {q1} kasus)<br>
            🟠 <b>Oranye</b> — Kasus sedang ({q1+1} – {q3} kasus)<br>
            🔴 <b>Merah</b> — Kasus tinggi ({q3+1} – {jumlah_max} kasus)<br>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_kanan:
    st.subheader("📊 Total Kasus per Kecamatan")

    clicked = map_data.get("last_object_clicked_popup")
    if clicked:
        match = re.search(
            r"📍 Kecamatan.*?<td>(.*?)</td>",
            str(clicked),
            re.DOTALL
        )
        if match:
            nama_klik = match.group(1).strip()
            row = df_year[df_year["kecamatan"] == nama_klik]
            if not row.empty:
                kasus = int(row["jumlah_kasus"].values[0])
                rank = int(
                    df_year["jumlah_kasus"]
                    .rank(ascending=False)
                    .loc[row.index[0]]
                )
                st.info(
                    f"**📍 {nama_klik}**\n\n"
                    f"🦠 Kasus TB Paru {selected_year}: **{kasus}**\n\n"
                    f"🏅 Peringkat: **{rank} dari {len(df_year)}**"
                )

    df_kecamatan = df_year.sort_values("jumlah_kasus", ascending=True)

    fig = px.bar(
        df_kecamatan,
        x="jumlah_kasus",
        y="kecamatan",
        color="jumlah_kasus",
        color_continuous_scale="YlOrRd",
        text="jumlah_kasus",
        orientation="h"
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=850,
        showlegend=False,
        coloraxis_showscale=False,
        xaxis_title="Jumlah Kasus",
        yaxis_title="Kecamatan",
        margin=dict(l=10, r=10, t=30, b=10)
    )

    st.plotly_chart(fig, width="stretch")

st.markdown("---")
st.subheader("🏆 10 Kecamatan dengan Kasus TB Paru Tertinggi")

top10 = df_year.sort_values("jumlah_kasus", ascending=False).head(10)

fig_top = px.bar(
    top10,
    x="kecamatan",
    y="jumlah_kasus",
    text="jumlah_kasus",
    color="jumlah_kasus",
    color_continuous_scale="Reds"
)
fig_top.update_traces(textposition="outside")
fig_top.update_layout(
    height=500,
    coloraxis_showscale=False,
    xaxis_title="Kecamatan",
    yaxis_title="Jumlah Kasus"
)
st.plotly_chart(fig_top, width="stretch")

st.markdown("---")
st.subheader("📋 Data Kecamatan")

filter_min, filter_max = st.slider(
    "Filter Jumlah Kasus",
    min_value=int(df_year["jumlah_kasus"].min()),
    max_value=int(df_year["jumlah_kasus"].max()),
    value=(
        int(df_year["jumlah_kasus"].min()),
        int(df_year["jumlah_kasus"].max())
    )
)

df_filtered = df_year[
    (df_year["jumlah_kasus"] >= filter_min) &
    (df_year["jumlah_kasus"] <= filter_max)
]

df_show = (
    df_filtered
    .sort_values("jumlah_kasus", ascending=False)
    .reset_index(drop=True)
)
df_show.index += 1
st.dataframe(df_show, width="stretch")

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center; padding:10px; line-height:2;">
        📌 <b>Source Data:</b> Dataset Kasus TB Paru Kota Bandung (TB_PARU.xlsx)
        &nbsp;|&nbsp;
        🗺️ <b>GeoJSON Peta:</b> Batas Kecamatan Kota Bandung
        <br>
        🔗 Referensi portal data resmi:
        <a href="https://opendata.bandung.go.id/" target="_blank">
            Open Data Kota Bandung
        </a>
        <br>
        👨‍💻 <b>Kontributor:</b> Achmad Muhajir
        &nbsp;|&nbsp;
        <a href="https://github.com/Dayyrenn" target="_blank">🔗 My GitHub</a>
    </div>
    """,
    unsafe_allow_html=True
)
