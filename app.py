# -*- coding: utf-8 -*-
import io
import json
from collections import defaultdict

import requests
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium
import plotly.express as px

st.set_page_config(page_title="Geopolítica de Ecuador (fuente oficial INEC)", page_icon="🌎", layout="wide")

# =========================================================
# 0) CONFIG: Servicio oficial (ArcGIS FeatureServer del INEC vía capa publicada)
#    -> Soporta f=geojson y outSR=4326 (lat/lon)
# =========================================================
PARROQUIAS_LAYER_URL = (
    "https://services7.arcgis.com/iFGeGXTAJXnjq0YN/ArcGIS/rest/services/"
    "Parroquias_del_Ecuador/FeatureServer/0/query"
)
# Campos clave en esa capa
FIELD_PROV = "DPA_DESPRO"   # Provincia (texto)
FIELD_CANT = "DPA_DESCAN"   # Cantón (texto)
FIELD_PARR = "DPA_DESPAR"   # Parroquia (texto)
FIELD_AREA = "AREA_KM2"     # Área km² (opcional)

# Región -> Provincias (catálogo simple)
REGIONES = {
    "Costa": ["Esmeraldas", "Manabí", "Santo Domingo De Los Tsáchilas", "Los Ríos", "Guayas", "Santa Elena", "El Oro"],
    "Sierra": ["Carchi", "Imbabura", "Pichincha", "Cotopaxi", "Tungurahua", "Bolívar", "Chimborazo", "Cañar", "Azuay", "Loja"],
    "Amazonía": ["Sucumbíos", "Napo", "Orellana", "Pastaza", "Morona Santiago", "Zamora Chinchipe"],
    "Insular (Galápagos)": ["Galápagos"],
}

# =========================================================
# 1) Utilidades de descarga y cache
# =========================================================
@st.cache_data(show_spinner=True)
def fetch_parroquias_geojson():
    """
    Descarga TODAS las parroquias (con provincia y cantón) desde el FeatureServer
    oficial (fuente INEC). Devuelve GeoJSON (EPSG:4326) y un DataFrame con atributos.
    """
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326",
    }
    r = requests.get(PARROQUIAS_LAYER_URL, params=params, timeout=60)
    r.raise_for_status()
    gj = r.json()

    # Extraer atributos tabulares para combos/tablas
    rows = []
    for f in gj.get("features", []):
        props = f.get("properties", {})
        rows.append({
            "Provincia": str(props.get(FIELD_PROV, "")).title(),
            "Cantón": str(props.get(FIELD_CANT, "")).title(),
            "Parroquia": str(props.get(FIELD_PARR, "")).title(),
            "Área_km2": props.get(FIELD_AREA, None),
        })
    df = pd.DataFrame(rows)
    return gj, df

@st.cache_data(show_spinner=False)
def build_prov_cant(df_parr: pd.DataFrame):
    """
    Construye diccionario {Provincia: [Cantones]} a partir del DataFrame de parroquias.
    """
    mapping = defaultdict(set)
    for _, r in df_parr.iterrows():
        prov = r["Provincia"]
        cant = r["Cantón"]
        if prov and cant:
            mapping[prov].add(cant)
    return {prov: sorted(list(cants)) for prov, cants in mapping.items()}

# =========================================================
# 2) Datos del usuario: Puntos geopolíticos e indicadores (overlay)
#    -> Se cargan desde literales JSON embebidos aquí (puedes moverlos a un .json)
# =========================================================
PUNTOS_GEO_JSON = {
  "puntos_geopoliticos":  [
    {"tipo":"Puerto Comercial","nombre":"Puerto de Guayaquil","ubicacion":{"lat":-2.2592,"lon":-79.9145},"descripcion":"Principal puerto del país, clave para el comercio exterior.","importancia":"Alta"},
    {"tipo":"Puerto Comercial","nombre":"Puerto de Esmeraldas","ubicacion":{"lat":0.9592,"lon":-79.65397},"descripcion":"Puerto multipropósito estratégico, cercano al Canal de Panamá (cercano a ciudad de Esmeraldas).","importancia":"Media"},
    {"tipo":"Puerto Comercial","nombre":"Puerto Bolívar","ubicacion":{"lat":-3.3456,"lon":-79.9983},"descripcion":"Segundo puerto bananero del país, clave para exportaciones agrícolas.","importancia":"Media"},
    {"tipo":"Refinería","nombre":"Refinería de Esmeraldas","ubicacion":{"lat":0.9634,"lon":-79.6644},"descripcion":"Principal refinería de petróleo de Ecuador.","importancia":"Alta"},
    {"tipo":"Extracción Petrolera","nombre":"Campos de Lago Agrio (Sucumbíos)","ubicacion":{"lat":0.1,"lon":-76.8},"descripcion":"Zona histórica y estratégica de extracción petrolera en la Amazonía.","importancia":"Alta"},
    {"tipo":"Extracción Petrolera","nombre":"Campo Sacha","ubicacion":{"lat":-0.3417,"lon":-77.1833},"descripcion":"Uno de los mayores y más antiguos campos petroleros con récord de producción.","importancia":"Alta"},
    {"tipo":"Extracción Petrolera","nombre":"Campo Pungarayacu (Bloque 20)","ubicacion":{"lat":-0.7,"lon":-77.8},"descripcion":"Campo de crudo pesado con reservas gigantes y producción significativa.","importancia":"Alta"},
    {"tipo":"Extracción Petrolera","nombre":"Bloque 43-ITT (Yasuní)","ubicacion":{"lat":-0.68,"lon":-76.43},"descripcion":"Bloque en reserva natural; en cierre progresivo tras referendo.","importancia":"Alta"},
    {"tipo":"Centro de Poder Político","nombre":"Palacio de Carondelet","ubicacion":{"lat":-0.2201,"lon":-78.5135},"descripcion":"Sede del Gobierno de la República del Ecuador.","importancia":"Alta"},
    {"tipo":"Extracción Minera","nombre":"Proyectos Mineros Mirador y Fruta del Norte","ubicacion":{"lat":-3.8823,"lon":-78.4907},"descripcion":"Proyectos de cobre y oro importantes para diversificación económica.","importancia":"Alta"},
    {"tipo":"Extracción Minera","nombre":"Proyecto La Plata","ubicacion":{"lat":-0.1,"lon":-78.8},"descripcion":"Depósito masivo de sulfuros ricos en oro, en fase de consulta ambiental.","importancia":"Media"},
    {"tipo":"Frontera Estratégica","nombre":"Puente Internacional de Rumichaca","ubicacion":{"lat":0.8256,"lon":-77.6593},"descripcion":"Principal punto de control fronterizo con Colombia, de alto flujo comercial y migratorio.","importancia":"Alta"},
    {"tipo":"Activo Estratégico","nombre":"Reserva Marina de Galápagos","ubicacion":{"lat":0.0,"lon":-90.0},"descripcion":"Reserva natural con valor ecológico global y gran zona económica exclusiva.","importancia":"Extrema"},
    {"tipo":"Infraestructura Aeroespacial / Militar","nombre":"Aeropuerto Internacional Eloy Alfaro (Base Aérea de Manta)","ubicacion":{"lat":-0.965,"lon":-80.705},"descripcion":"Infraestructura estratégica aérea y naval; hasta 2009 funcionó una base militar extranjera.","importancia":"Alta"},
    {"tipo":"Estación Científica","nombre":"Base Pedro Vicente Maldonado (Antártida)","ubicacion":{"lat":-62.5,"lon":-59.7},"descripcion":"Estación antártica ecuatoriana en isla Greenwich, presencia estratégica en la Antártida.","importancia":"Media-Alta"},
    {"tipo":"Infraestructura Energética","nombre":"Central Térmica Esmeraldas I","ubicacion":{"lat":0.9167,"lon":-79.6667},"descripcion":"Central térmica a vapor de 130 MW, operativa desde 1982.","importancia":"Alta"},
    {"tipo":"Infraestructura Energética","nombre":"Central Térmica Esmeraldas II","ubicacion":{"lat":0.9167,"lon":-79.6667},"descripcion":"Central térmica de 96 MW operativa desde 2014.","importancia":"Alta"},
    {"tipo":"Infraestructura Energética","nombre":"Central Hidroeléctrica Coca Codo Sinclair","ubicacion":{"lat":-0.1993,"lon":-77.6839},"descripcion":"Planta hidroeléctrica más grande del país (1 500 MW), entre Napo y Sucumbíos.","importancia":"Alta"}
  ]
}

INDICADORES_SEG = [
    {"provincia":"Guayas","indice_riesgo":9,"factores":["Delincuencia organizada","Narcotráfico","Conflicto de bandas","Control de rutas portuarias"]},
    {"provincia":"Esmeraldas","indice_riesgo":10,"factores":["Disputas territoriales","Presencia de grupos armados irregulares","Narcotráfico","Control de la frontera"]},
    {"provincia":"Manabí","indice_riesgo":8,"factores":["Delincuencia organizada","Puntos de desembarque de drogas"]},
    {"provincia":"El Oro","indice_riesgo":8,"factores":["Narcotráfico","Contrabando","Actividad criminal en el puerto"]},
    {"provincia":"Santo Domingo De Los Tsáchilas","indice_riesgo":8,"factores":["Delincuencia común y organizada","Corredor de transporte de sustancias ilícitas"]},
    {"provincia":"Sucumbíos","indice_riesgo":10,"factores":["Narcotráfico","Presencia de grupos armados en la frontera con Colombia"]},
    {"provincia":"Pichincha","indice_riesgo":7,"factores":["Delincuencia común y organizada","Extorsión"]},
    {"provincia":"Carchi","indice_riesgo":8,"factores":["Narcotráfico","Punto de migración irregular","Control de fronteras"]},
    {"provincia":"Azuay","indice_riesgo":4,"factores":["Delincuencia común"]},
    {"provincia":"Loja","indice_riesgo":3,"factores":["Bajo nivel de delincuencia"]},
    {"provincia":"Galápagos","indice_riesgo":2,"factores":["Bajo nivel de delincuencia","Control marítimo"]},
    {"provincia":"Napo","indice_riesgo":6,"factores":["Tráfico de drogas"]},
    {"provincia":"Pastaza","indice_riesgo":5,"factores":["Conflictos por territorio"]},
    {"provincia":"Morona Santiago","indice_riesgo":4,"factores":["Disputas por minería ilegal"]},
    {"provincia":"Orellana","indice_riesgo":7,"factores":["Delincuencia organizada en torno a actividad petrolera"]},
    {"provincia":"Zamora Chinchipe","indice_riesgo":6,"factores":["Conflictos por minería ilegal"]},
    {"provincia":"Los Ríos","indice_riesgo":7,"factores":["Delincuencia organizada","Conflictos agrícolas"]},
    {"provincia":"Cañar","indice_riesgo":4,"factores":["Delincuencia común"]},
    {"provincia":"Chimborazo","indice_riesgo":5,"factores":["Delincuencia común"]},
    {"provincia":"Cotopaxi","indice_riesgo":5,"factores":["Delincuencia común"]},
    {"provincia":"Imbabura","indice_riesgo":4,"factores":["Delincuencia común"]},
    {"provincia":"Tungurahua","indice_riesgo":3,"factores":["Delincuencia común"]},
    {"provincia":"Bolívar","indice_riesgo":2,"factores":["Bajo nivel de delincuencia"]},
    {"provincia":"Santa Elena","indice_riesgo":5,"factores":["Delincuencia común","Control de rutas"]}
]

# =========================================================
# 3) UI Lateral
# =========================================================
st.sidebar.title("⚙️ Controles")
st.sidebar.caption("Datos administrativos desde servicio oficial (capa parroquias con campos de provincia y cantón).")
nivel = st.sidebar.radio("Nivel de visualización", ["Provincias", "Cantones", "Parroquias"], index=0)
region = st.sidebar.selectbox("Región", list(REGIONES.keys()))
mostrar_puntos = st.sidebar.checkbox("Mostrar puntos geopolíticos (capa propia)", value=True)
mostrar_indic = st.sidebar.checkbox("Mostrar indicadores de seguridad (tabla/gráfico)", value=True)

# =========================================================
# 4) Carga de datos oficiales (INEC vía FeatureServer) + catálogos
# =========================================================
gj_parr, df_parr = fetch_parroquias_geojson()
PROV_CANT = build_prov_cant(df_parr)

# Catálogos dinámicos por región
provincias_region = sorted(REGIONES[region])
provincia = st.sidebar.selectbox("Provincia", ["(Todas)"] + provincias_region)
cantones = PROV_CANT.get(provincia, []) if provincia != "(Todas)" else []
canton = st.sidebar.selectbox("Cantón", ["(Todos)"] + cantones) if cantones else "(Todos)"

with st.sidebar.expander("Descargas / Exportar"):
    exportar = st.checkbox("Habilitar exportación CSV")

# =========================================================
# 5) Encabezado
# =========================================================
st.title("🌎 Estructura geopolítica del Ecuador — Fuente oficial INEC")
st.markdown(
    "Los polígonos provienen de un **FeatureServer** cuya descripción cita explícitamente al **INEC**. "
    "Se filtran por **Región → Provincia → Cantón → Parroquia** y se muestran en un mapa con tabla y jerarquía."
)
st.caption("Servicio: Parroquias del Ecuador (FeatureServer, soporta GeoJSON).")

# =========================================================
# 6) Filtrado y armado de la capa visible
# =========================================================
def feature_matches(props: dict) -> bool:
    prov = str(props.get(FIELD_PROV, "")).title()
    cant = str(props.get(FIELD_CANT, "")).title()
    parr = str(props.get(FIELD_PARR, "")).title()

    # Filtro por región
    if prov not in provincias_region:
        return False

    # Filtro por provincia
    if provincia != "(Todas)" and prov != provincia:
        return False

    # Filtro por cantón
    if nivel in ("Cantones", "Parroquias") and canton != "(Todos)" and cant != canton:
        return False

    # A nivel Provincias/Cantones mostramos todas las parroquias que caen dentro del filtro
    return True

filtered_features = []
for f in gj_parr.get("features", []):
    props = f.get("properties", {})
    if feature_matches(props):
        filtered_features.append(f)

if not filtered_features:
    st.warning("No hay resultados con los filtros actuales.")
    st.stop()

# =========================================================
# 7) KPIs
# =========================================================
col1, col2, col3 = st.columns(3)
col1.metric("Nivel", nivel)
col2.metric("Región", region)
col3.metric("Elementos visibles", len(filtered_features))

# =========================================================
# 8) Mapa (Folium) + puntos geopolíticos
# =========================================================
map_center = [-1.8312, -78.1834]  # Ecuador aprox
m = folium.Map(location=map_center, zoom_start=6, control_scale=True, tiles="cartodbpositron")

# Etiqueta según nivel
if nivel == "Provincias":
    label_field = FIELD_PROV
elif nivel == "Cantones":
    label_field = FIELD_CANT
else:
    label_field = FIELD_PARR

# Capa polígonos (sin disolver; se usan polígonos parroquiales filtrados)
folium.GeoJson(
    {"type": "FeatureCollection", "features": filtered_features},
    name="Límites",
    tooltip=folium.GeoJsonTooltip(fields=[label_field, FIELD_PROV, FIELD_CANT, FIELD_PARR],
                                  aliases=["Nombre:", "Provincia:", "Cantón:", "Parroquia:"]),
    highlight_function=lambda x: {"weight": 3},
    zoom_on_click=True,
).add_to(m)

# Puntos geopolíticos (overlay propio)
if mostrar_puntos:
    fg = folium.FeatureGroup(name="Puntos geopolíticos (propios)")
    for p in PUNTOS_GEO_JSON["puntos_geopoliticos"]:
        lat = p["ubicacion"]["lat"]
        lon = p["ubicacion"]["lon"]
        popup = folium.Popup(f"<b>{p['nombre']}</b><br/>{p['tipo']}<br/>{p['descripcion']}<br/><i>Importancia: {p['importancia']}</i>", max_width=350)
        folium.CircleMarker(location=[lat, lon], radius=5, popup=popup).add_to(fg)
    fg.add_to(m)

folium.LayerControl().add_to(m)
with st.container(border=True):
    st.subheader("🗺️ Mapa")
    st_folium(m, height=540, use_container_width=True)

# =========================================================
# 9) Tabla y jerarquía (Sunburst)
# =========================================================
rows = []
for f in filtered_features:
    props = f.get("properties", {})
    rows.append({
        "Provincia": str(props.get(FIELD_PROV, "")).title(),
        "Cantón": str(props.get(FIELD_CANT, "")).title(),
        "Parroquia": str(props.get(FIELD_PARR, "")).title(),
        "Área (km²)": props.get(FIELD_AREA, None),
    })
df = pd.DataFrame(rows)

tab1, tab2 = st.tabs(["📋 Tabla", "🌞 Jerarquía"])
with tab1:
    st.dataframe(df.sort_values(["Provincia","Cantón","Parroquia"]), use_container_width=True, hide_index=True)
    if exportar:
        buff = io.StringIO()
        df.to_csv(buff, index=False)
        st.download_button("⬇️ Descargar CSV", buff.getvalue(), "ecuador_geopolitica_oficial.csv", mime="text/csv")

with tab2:
    if nivel == "Provincias":
        fig = px.sunburst(df, path=["Provincia"], values="Área (km²)", width=850, height=560)
    elif nivel == "Cantones":
        fig = px.sunburst(df, path=["Provincia", "Cantón"], values="Área (km²)", width=850, height=560)
    else:
        fig = px.sunburst(df, path=["Provincia", "Cantón", "Parroquia"], values="Área (km²)", width=850, height=560)
    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# 10) Indicadores de seguridad (propios)
# =========================================================
if mostrar_indic:
    st.subheader("🛡️ Indicadores de seguridad (capa propia)")
    df_ind = pd.DataFrame(INDICADORES_SEG)
    df_ind["factores"] = df_ind["factores"].apply(lambda xs: "; ".join(xs))
    st.dataframe(df_ind.rename(columns={"provincia":"Provincia","indice_riesgo":"Índice de riesgo","factores":"Factores"}), use_container_width=True, hide_index=True)

    st.markdown("**Top 10 por índice de riesgo**")
    df_top = df_ind.sort_values("indice_riesgo", ascending=False).head(10)
    fig2 = px.bar(df_top, x="provincia", y="indice_riesgo", title="", labels={"provincia":"Provincia","indice_riesgo":"Índice"})
    st.plotly_chart(fig2, use_container_width=True)

# =========================================================
# 11) Ficha informativa
# =========================================================
with st.expander("ℹ️ Notas y fuente de datos"):
    st.markdown(
        "- **Polígonos administrativos**: descargados en tiempo real desde un **FeatureServer ArcGIS** cuya "
        "descripción indica que la capa proviene del **INEC** (Clasificador Geográfico Estadístico / DPA). "
        "Se usa el nivel Parroquia y se filtra por Provincia/Cantón según el nivel seleccionado. "
        "Esto garantiza una **única fuente oficial** para toda la jerarquía. "
        "\n- **Puntos geopolíticos** e **indicadores**: provistos en esta app como datos propios (puedes sustituirlos por fuentes ministeriales cuando las tengas)."
    )
