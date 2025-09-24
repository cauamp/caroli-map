from geopy.geocoders import Nominatim
import dash
import dash_leaflet as dl
from dash import html
import json
import pandas as pd

df = pd.read_csv("parsed_cities.csv")
cities = df["city"].tolist()

# Tenta carregar backup primeiro
try:
    with open("./cities_backup.json", "r", encoding="utf-8") as backup_file:
        coords = json.load(backup_file)
    print("📁 Carregado coordenadas do backup")
except FileNotFoundError:
    # Inicializa geocodificador
    geolocator = Nominatim(user_agent="city_mapper")

    # Busca coordenadas
    coords = {}
    for city in cities:
        location = geolocator.geocode(f"{city}, Brazil")
        if location:
            coords[city] = (location.latitude, location.longitude)
        else:
            print(f"⚠️ Não encontrei {city}")

    # Salva backup
    with open("./cities_backup.json", "w", encoding="utf-8") as backup_file:
        json.dump(coords, backup_file, ensure_ascii=False, indent=2)
    print("💾 Backup salvo")

# Adiciona coluna com coordenadas
df["coords"] = df["city"].map(lambda city: tuple(coords.get(city, (None, None))))

# Preenche campos vazios
df["organization_name"] = df["organization_name"].fillna("")
df["description"] = df["description"].fillna("")
df["img"] = df["img"].fillna("")

# Ícone customizado
custom_icon = {
    "iconUrl": "https://cdn-icons-png.flaticon.com/512/854/854878.png",
    "iconSize": [30, 30],
    "iconAnchor": [15, 30],
    "popupAnchor": [0, -30],
}

# Cria marcadores
markers = [
    dl.Marker(
        position=row["coords"],
        icon=custom_icon,
        children=[
            dl.Tooltip(row["organization_name"] if row["organization_name"] else row["city"]),
            dl.Popup(
                [
                    html.H3(
                        row["organization_name"] if row["organization_name"] else row["city"],
                        style={"textAlign": "center", "margin": "5px 0"},
                    ),
                    html.P(row["description"], style={"textAlign": "justify"}),
                    html.Img(
                        src=row["img"],
                        style={"width": "250px", "height": "auto", "display": "block", "margin": "0 auto"},
                    )
                    if row["img"]
                    else None,
                ]
            ),
        ],
    )
    for _, row in df.iterrows()
    if row["coords"] != (None, None)
]

# App Dash
app = dash.Dash(__name__, title="Bebês em Espaços Coletivos")
app.index_string = app.index_string.replace("favicon.ico", "favicon.png")

app.layout = html.Div(
    style={
        "backgroundColor": "#f3a9d1",  # light gray background
        "minHeight": "100vh",  # full page height
        "padding": "20px",  # margin inside
        "fontFamily": "Arial, sans-serif",
    },
    children=[
        html.H1(
            "Bebês em Espaços Coletivos no Brasil",
            style={
                "textAlign": "center",
                "color": "#ffffff",
                "marginBottom": "20px",
            },
        ),
        html.Div(
            style={
                "maxWidth": "1000px",  # center the content
                "margin": "0 auto",  # center horizontally
                "padding": "10px",
                "backgroundColor": "#74c5cb",  # white background for the map container
                "boxShadow": "0px 4px 12px rgba(0,0,0,0.1)",
                "borderRadius": "10px",
            },
            children=[
                dl.Map(
                    center=[-15.0, -55.0],
                    zoom=4,
                    bounds=[[-35.0, -75.0], [5.0, -30.0]],  # limites do Brasil
                    maxBounds=[[-35.0, -75.0], [5.0, -30.0]],
                    maxBoundsViscosity=1.0,
                    style={"width": "100%", "height": "600px", "borderRadius": "10px"},
                    children=[
                        dl.TileLayer(
                            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
                        ),
                        dl.FeatureGroup(markers),
                    ],
                )
            ],
        ),
    ],
)

server = app.server  # 👈 important for Render / Gunicorn

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
