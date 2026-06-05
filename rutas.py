from flask import Flask, render_template, request, jsonify
import osmnx as ox
import heapq

app = Flask(__name__)


# ── A* implementado desde cero ──────────────────────────────────────────────
def imprimir_calles(G, ruta):
    print("\n--- Ruta calculada ---")
    calle_actual = None
    contador = 1
    for i in range(len(ruta) - 1):
        u, v = ruta[i], ruta[i + 1]
        datos = G[u][v]
        # tomar la primera arista disponible
        arista = list(datos.values())[0]
        nombre = arista.get('name', 'Sin nombre')
        # si es lista tomar el primero
        if isinstance(nombre, list):
            nombre = nombre[0]
        # solo imprimir cuando cambia la calle
        if nombre != calle_actual:
            print(f"  {contador}. {nombre}")
            calle_actual = nombre
            contador += 1
    print("----------------------\n")

def astar(G, origen, destino):
    def h(u):
        return ox.distance.great_circle(
            G.nodes[u]['y'], G.nodes[u]['x'],
            G.nodes[destino]['y'], G.nodes[destino]['x']
        )

    open_set = []
    heapq.heappush(open_set, (0, origen))
    g = {origen: 0}
    came_from = {origen: None}

    while open_set:
        _, actual = heapq.heappop(open_set)

        if actual == destino:
            ruta = []
            while actual is not None:
                ruta.append(actual)
                actual = came_from[actual]
            ruta.reverse()
            return ruta

        for vecino, aristas in G[actual].items():
            longitud = min(d.get('length', 1) for d in aristas.values())
            g_nuevo = g[actual] + longitud

            if vecino not in g or g_nuevo < g[vecino]:
                g[vecino] = g_nuevo
                f = g_nuevo + h(vecino)
                heapq.heappush(open_set, (f, vecino))
                came_from[vecino] = actual

    return None


def cargar_grafo(lat_o, lng_o, lat_d, lng_d):
    margen = 0.01
    north = max(lat_o, lat_d) + margen
    south = min(lat_o, lat_d) - margen
    east  = max(lng_o, lng_d) + margen
    west  = min(lng_o, lng_d) - margen
    bbox  = (west, south, east, north)
    return ox.graph_from_bbox(bbox, network_type="drive")


def calcular_distancia(G, ruta):
    total = 0
    for i in range(len(ruta) - 1):
        u, v = ruta[i], ruta[i + 1]
        aristas = G[u][v]
        total += min(d.get('length', 0) for d in aristas.values())
    return total


# ── Rutas Flask ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ruta', methods=['POST'])
def calcular_ruta():
    data = request.get_json()
    origen_str  = data.get('origen', '').strip()
    destino_str = data.get('destino', '').strip()

    if not origen_str or not destino_str:
        return jsonify({'error': 'Origen y destino son obligatorios.'}), 400

    # Geocodificar
    try:
        lat_o, lng_o = ox.geocode(origen_str)
    except Exception:
        return jsonify({'error': f'No se encontro el origen: "{origen_str}"'}), 400

    try:
        lat_d, lng_d = ox.geocode(destino_str)
    except Exception:
        return jsonify({'error': f'No se encontro el destino: "{destino_str}"'}), 400

    # Cargar grafo dinamico segun los puntos
    try:
        G = cargar_grafo(lat_o, lng_o, lat_d, lng_d)
    except Exception as e:
        return jsonify({'error': f'Error al cargar el mapa: {str(e)}'}), 500

    # Nodos mas cercanos
    nodo_origen  = ox.nearest_nodes(G, lng_o, lat_o)
    nodo_destino = ox.nearest_nodes(G, lng_d, lat_d)

    # Calcular ruta con A*
    ruta = astar(G, nodo_origen, nodo_destino)

    if ruta is None:
        return jsonify({'error': 'No se encontro ruta entre los puntos indicados.'}), 404

    print(f"Origen:  {origen_str}")
    print(f"Destino: {destino_str}")
    imprimir_calles(G, ruta)#Debbugin

    # Convertir nodos a coordenadas para el mapa
    coords = []
    for i in range(len(ruta) - 1):
        u, v = ruta[i], ruta[i + 1]
        arista = list(G[u][v].values())[0]
        if 'geometry' in arista:
            puntos = [(lat, lng) for lng, lat in arista['geometry'].coords]
            coords.extend(puntos)
        else:
            coords.append([G.nodes[u]['y'], G.nodes[u]['x']])
    coords.append([G.nodes[ruta[-1]]['y'], G.nodes[ruta[-1]]['x']])
    distancia = calcular_distancia(G, ruta)

    return jsonify({
        'ruta':        coords,
        'nodos':       len(ruta),
        'distancia_m': round(distancia, 2)
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
