import json
import math
import os
from collections import defaultdict

import dash
import dash_leaflet as dl
import pandas as pd
from dash import Input, Output, dcc, html
from dotenv import load_dotenv
from geopy.geocoders import Nominatim

load_dotenv()

CARTO_TILE_KEY = os.environ["CARTO_TILE_KEY"]

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

# Distribui as organizações que compartilham a mesma coordenada (ex.: várias na
# mesma cidade) num pequeno círculo, para os pins não ficarem exatamente um em
# cima do outro. Determinístico e calculado uma única vez: cada organização
# ocupa sempre o mesmo ponto em todas as páginas.
RING_RADIUS = 0.04  # graus (~4,4 km); só se separa visualmente com zoom


def _spread_overlapping(coords_series):
    groups = defaultdict(list)
    for idx, coord in coords_series.items():
        if coord != (None, None):
            groups[coord].append(idx)
    result = coords_series.copy()
    for coord, idxs in groups.items():
        if len(idxs) < 2:
            continue  # só uma organização nesta coordenada: mantém o centro
        lat0, lon0 = coord
        lon_corr = max(math.cos(math.radians(lat0)), 0.1)  # círculo visualmente redondo
        for k, idx in enumerate(idxs):
            ang = 2 * math.pi * k / len(idxs)
            result.at[idx] = (
                lat0 + RING_RADIUS * math.sin(ang),
                lon0 + RING_RADIUS * math.cos(ang) / lon_corr,
            )
    return result


df["marker_coords"] = _spread_overlapping(df["coords"])

# Ícones dos marcadores (SVG). O ponto do pin fica na base central.
PIN_ICON = {
    "iconUrl": "/assets/pin.svg",
    "iconSize": [25, 35],
    "iconAnchor": [15, 42],
    "popupAnchor": [0, -42],
}
# A "Casa da Infância – UFMG" usa um pin próprio, um pouco maior para destaque.
CASA_INFANCIA_ID = "Casa da Infância – UFMG"
PIN_CASA_ICON = {
    "iconUrl": "/assets/pin_casaDaInfancia.svg",
    "iconSize": [31, 44],
    "iconAnchor": [19, 53],
    "popupAnchor": [0, -53],
}


# Cria marcadores. Quando clickable=False, os marcadores não respondem a
# cliques/hover (sem popup nem tooltip) — mapa apenas ilustrativo.
def build_markers(clickable=True):
    result = []
    for _, row in df.iterrows():
        if row["marker_coords"] == (None, None):
            continue
        name = row["organization_name"] if row["organization_name"] else row["city"]
        children = []
        if clickable:
            children = [
                dl.Tooltip(name),
                dl.Popup(
                    [
                        html.H3(name, style={"textAlign": "center", "margin": "5px 0"}),
                        html.P(row["description"], style={"textAlign": "justify"}),
                        html.Img(
                            src=row["img"],
                            style={"width": "250px", "height": "auto", "display": "block", "margin": "0 auto"},
                        )
                        if row["img"]
                        else None,
                    ]
                ),
            ]
        is_casa = row["organization_name"] == CASA_INFANCIA_ID
        icon = PIN_CASA_ICON if is_casa else PIN_ICON
        result.append(
            dl.Marker(
                position=row["marker_coords"],
                icon=icon,
                interactive=clickable,
                # mantém a Casa da Infância sempre acima dos marcadores vizinhos
                zIndexOffset=1000 if is_casa else 0,
                children=children,
            )
        )
    return result


# -----------------------------------------------------------------------------
# Cores e conteúdo (baseados no design.pdf)
# -----------------------------------------------------------------------------
HEADER_YELLOW = "#FBD44C"
CARD_YELLOW = "#FBF0B0"
CARD_BLUE = "#79B7D6"
CARD_PURPLE = "#8A8FE0"
CARD_PINK = "#F5A6A0"
PAGE1_BG = "#F5A79E"  # coral
PAGE2_BG = "#86DBA0"  # verde
PAGE3_BG = "#A9D3EA"  # azul claro

TITLE = "MAPA DE PRÁTICAS DE FOMENTO AO DESENVOLVIMENTO INFANTIL NO CENÁRIO NACIONAL"


def build_map(interactive=True, legend=None):
    """Cria o mapa do Brasil. Quando interactive=False, as interações
    (arrastar, zoom, controles) e os cliques nos marcadores ficam travados.
    Se `legend` for informado, sobrepõe um aviso no canto do mapa."""
    locked = (
        {}
        if interactive
        else {
            "dragging": False,
            "scrollWheelZoom": False,
            "doubleClickZoom": False,
            "boxZoom": False,
            "keyboard": False,
            "touchZoom": False,
            "zoomControl": False,
        }
    )
    the_map = dl.Map(
        center=[-15.0, -55.0],
        zoom=5,
        bounds=[[-35.0, -75.0], [5.0, -30.0]],  # limites do Brasil
        maxBounds=[[-35.0, -75.0], [5.0, -30.0]],
        maxBoundsViscosity=1.0,
        style={"width": "100%", "height": "100%", "borderRadius": "12px"},
        children=[
            dl.TileLayer(
                url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=" + CARTO_TILE_KEY,
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            ),
            dl.FeatureGroup(build_markers(clickable=interactive)),
        ],
        **locked,
    )
    if not legend:
        return the_map
    return html.Div(
        [
            the_map,
            html.Div(
                legend,
                style={
                    "position": "absolute",
                    "bottom": "14px",
                    "left": "14px",
                    "zIndex": "1000",
                    "backgroundColor": "rgba(255,255,255,0.92)",
                    "color": "#2b2b2b",
                    "fontFamily": "'Providence Sans', 'Segoe UI', sans-serif",
                    "fontSize": "14px",
                    "fontStyle": "italic",
                    "padding": "8px 14px",
                    "borderRadius": "12px",
                    "boxShadow": "0 2px 6px rgba(0,0,0,0.18)",
                },
            ),
        ],
        style={"position": "relative", "height": "100%", "width": "100%"},
    )


def header():
    return html.Div(
        [
            html.Span(TITLE, style={"letterSpacing": "1px"}),
            html.Img(
                src="/assets/icon.svg",
                style={"height": "88px", "marginLeft": "18px", "flexShrink": "0"},
            ),
        ],
        className="app-header",
        style={
            "backgroundColor": HEADER_YELLOW,
            "color": "#2b2b2b",
            "fontFamily": "'Pangolin', 'Comic Sans MS', cursive",
            "fontWeight": "bold",
            "fontSize": "18px",
            "padding": "18px 24px",
            "borderRadius": "16px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
        },
    )


def card(children, bg, color="#2b2b2b", grow=1, extra_style=None):
    style = {
        "backgroundColor": bg,
        "color": color,
        "fontFamily": "'Providence Sans', 'Segoe UI', sans-serif",
        "padding": "12px",
        "borderRadius": "18px",
        "lineHeight": "1.5",
        "fontStyle": "italic",
        "boxSizing": "border-box",
        "fontSize": "18px",
    }
    if grow:
        # cresce para ocupar a altura disponível; rola se o texto passar
        style.update({"flex": str(grow), "minHeight": "0", "overflowY": "auto"})
    if extra_style:
        style.update(extra_style)
    return html.Div(children, style=style)


def clickable_card(children, href, bg, color="#2b2b2b", grow=1):
    """Card inteiro clicável que navega para outra página."""
    return dcc.Link(
        card(
            children,
            bg,
            color,
            grow=0,
            extra_style={"cursor": "pointer", "height": "100%", "overflowY": "auto"},
        ),
        href=href,
        style={
            "textDecoration": "none",
            "color": "inherit",
            "flex": str(grow),
            "minHeight": "0",
            "display": "flex",
        },
    )


# Visual único para todos os botões/links (mesma linguagem do design)
PILL_STYLE = {
    "backgroundColor": HEADER_YELLOW,
    "color": "#2b2b2b",
    "fontFamily": "'Pangolin', 'Comic Sans MS', cursive",
    "fontWeight": "bold",
    "padding": "14px 20px",
    "borderRadius": "14px",
    "textDecoration": "none",
    "textAlign": "center",
    "boxSizing": "border-box",
    "boxShadow": "0 2px 6px rgba(0,0,0,0.12)",
}


def download_button():
    return html.A(
        ["BAIXE O TRABALHO ESCRITO AQUI ⬇"],
        href="#",
        className="pill",
        style={**PILL_STYLE, "display": "block"},
    )


def home_button():
    """Botão de navegação de volta à página inicial (páginas internas)."""
    return dcc.Link(
        ["⬅ VOLTAR AO INÍCIO"],
        href="/",
        className="pill",
        style={**PILL_STYLE, "display": "block"},
    )


def cta_pill(text):
    """Chamada visível de 'link' dentro de um card clicável. É um <span>
    (não uma âncora) porque o card inteiro já é um dcc.Link."""
    return html.Span(
        [text, " ➜"],
        className="pill",
        style={**PILL_STYLE, "display": "inline-block", "marginTop": "16px"},
    )


def page_shell(
    bg,
    map_component,
    right_children,
    width_ratio=(
        5,
        2,
    ),
):
    return html.Div(
        className="shell",
        style={
            "backgroundColor": bg,
            "height": "100vh",
            "padding": "20px",
            "boxSizing": "border-box",
            "fontFamily": "'Comic Sans MS', 'Segoe UI', sans-serif",
            "display": "flex",
            "gap": "20px",
        },
        children=[
            # Coluna esquerda: cabeçalho (só a largura do mapa) + mapa
            html.Div(
                className="col-left",
                style={
                    "flex": str(width_ratio[0]),
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "20px",
                    "minHeight": "0",
                },
                children=[
                    header(),
                    html.Div(
                        map_component,
                        className="map-frame",
                        style={
                            "flex": "1",
                            "minHeight": "0",
                            "backgroundColor": "#ffffff",
                            "padding": "22px",
                            "borderRadius": "18px",
                            "boxSizing": "border-box",
                        },
                    ),
                ],
            ),
            # Coluna direita: cards preenchendo toda a altura
            html.Div(
                right_children,
                className="col-right",
                style={
                    "flex": str(width_ratio[1]),
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "20px",
                    "minHeight": "0",
                },
            ),
        ],
    )


# -----------------------------------------------------------------------------
# Páginas
# -----------------------------------------------------------------------------
def page_home():
    yellow = clickable_card(
        [
            "Este Mapa é fruto de um trabalho de Iniciação Científica desenvolvido "
            "pela estudante de graduação em Pedagogia pela Faculdade Federal de Minas "
            "Gerais (UFMG), Laura Caroli orientada pela professora Vanessa Neves, do "
            "grupo de pesquisa Estudos em Cultura, Educação e Infância (ElaCei) para a "
            "pesquisa: Espaços de Fomento de Desenvolvimento Infantil no Brasil: Um "
            "levantamento de práticas no cenário nacional. ",
            html.Br(),
            cta_pill("Clique aqui para saber mais"),
        ],
        href="/sobre",
        bg=CARD_YELLOW,
    )
    blue = clickable_card(
        [
            "Ao decorrer da pesquisa foi desenvolvida uma tabela com todas as "
            "instituições levantadas o que permitiu que fosse feita uma análise "
            "estatística sobre o vínculo institucional ou a data de inauguração dos "
            "projetos. ",
            html.Br(),
            cta_pill("Para explorar mais, clique aqui"),
        ],
        href="/analise",
        bg=CARD_BLUE,
        color="#ffffff",
    )
    return page_shell(PAGE1_BG, build_map(interactive=False), [yellow, blue])


def page_analise():
    purple = card(
        "A partir das 34 iniciativas encontradas, a filtragem feita delimitou uma "
        "Tabela Principal com 26 instituições apresentadas no site, entre outras 4 "
        "Escolas de Aplicação e 5 Menções Honrosas de projetos itinerantes ou virtuais.",
        CARD_PURPLE,
        color="#ffffff",
    )
    pink = card(
        "A análise quantitativa revelou que 19,2% das frentes pertencem a "
        "universidades públicas, 7,7% a equipamentos municipais e 69,2% ao terceiro "
        "setor (ONGs/OSCs). Os eixos de ação principais abrangem: 26,9% em "
        "Desenvolvimento Comunitário, 15,4% em Linguagem Artística, 15,4% em Brincar e "
        "Sensorialidade, 15,4% em Mediação de Leitura e 11,5% em Contato com a "
        "Natureza. A matriz de coocorrência aponta que 73,1% a atuação das iniciativas "
        "ocorrem de forma híbrida, com forte cruzamento entre Pesquisa/Advocacy, "
        "Formação de Educadores e do estímulo do Brincar.",
        CARD_PINK,
        grow=2,
    )
    return page_shell(
        PAGE2_BG,
        build_map(interactive=True, legend="📍 Dê um zoom e clique em um marcador para saber mais!"),
        [home_button(), purple, pink, download_button()],
    )


def page_sobre():
    paragraphs = [
        "Este Mapa é fruto de um relatório de iniciação científica desenvolvida pela estudante de graduação em Pedagogia pela Universidade Federal de Minas Gerais (UFMG), Laura Caroli orientada pela professora Vanessa Neves, do grupo de pesquisa Estudos em Cultura, Educação e Infância (ElaCei) para a pesquisa: Espaços de Fomento de Desenvolvimento Infantil no Brasil: Um levantamento de práticas no cenário nacional. \n",
        "Com carater qualitativo-exploratório, esta pesquisa de mapeamento se dedica a investigar e mapear espaços focados na primeira infância e em fomentar diferentes processos para seu desenvolvimento, tendo como referência central a proposta da Casa da Infância da UFMG e o tripé acadêmico de ensino, pesquisa e extensão. \n",
        "A metodologia estruturou-se em frentes de levantamentos, buscas manuais, contatos institucionais com universidades e iniciativas, entrevistas semiestruturadas com coordenadoras de dois espaços (LabEdu e CPAPI) e uma visita presencial com notas em diário de campo (CRIAR Recife). Os dados coletados de 34 organizações foram sistematizados em uma planilha, permitindo plotar um mapa interativo e classificar e analisar 26 iniciativas. Os resultados apontam um panorama nacional bem diverso, onde há projetos com diferentes objetivos, e estes se concentram em frentes como a extensão social, na formação continuada de adultos, laboratórios universitários, entre outros.\n",
    ]
    big_card = card(
        [html.P(p, style={"margin": "0 0 14px 0"}) for p in paragraphs] + [download_button()],
        CARD_YELLOW,
        extra_style={"height": "100%", "overflowY": "auto"},
    )
    return page_shell(PAGE3_BG, build_map(interactive=False), [home_button(), big_card], width_ratio=(3, 2))


# -----------------------------------------------------------------------------
# App Dash + roteamento
# -----------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    title="MAPA DE PRÁTICAS DE FOMENTO AO DESENVOLVIMENTO INFANTIL NO CENÁRIO NACIONAL",
    suppress_callback_exceptions=True,
    external_stylesheets=["https://fonts.googleapis.com/css2?family=Pangolin&display=swap"],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
# Favicon: .ico raster para o Safari (que rasteriza SVG sobre fundo branco)
# e o SVG para navegadores modernos (Chrome/Brave/Firefox), que o preferem.
app.index_string = app.index_string.replace(
    "{%favicon%}",
    '<link rel="icon" href="/assets/logo_square.ico?v=2" sizes="32x32">'
    '<link rel="icon" type="image/svg+xml" href="/assets/logo_circle.svg?v=2">',
)

app.layout = html.Div([dcc.Location(id="url"), html.Div(id="page-content")])


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(pathname):
    if pathname == "/analise":
        return page_analise()
    if pathname == "/sobre":
        return page_sobre()
    return page_home()


server = app.server  # 👈 important for Render / Gunicorn

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
