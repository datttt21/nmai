from flask import Flask, render_template, request, jsonify, url_for, redirect, session
import osmnx as ox
import networkx as nx
import os
import shutil
from shortest_path import *

app = Flask(__name__)
app.secret_key = 'your_secret_key'
banned_edges = []
banned_areas = []

congvi_map = ox.load_graphml('congvi_badinh_hanoi_graph.graphml')
G = Create_simple_Graph(congvi_map)

@app.route('/')
def index():
    node_coords = [(congvi_map.nodes[node]['y'], congvi_map.nodes[node]['x']) for node in congvi_map.nodes]
    path_coords = [
        [(congvi_map.nodes[e[0]]['y'], congvi_map.nodes[e[0]]['x']), (congvi_map.nodes[e[1]]['y'], congvi_map.nodes[e[1]]['x'])]
        for e in congvi_map.edges
    ]
    return render_template('index.html', node_coords=node_coords, path_coords=path_coords)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error='Sai tài khoản hoặc mật khẩu!')
    return render_template('admin_login.html')

@app.route('/admin/panel')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    node_coords = [(congvi_map.nodes[node]['y'], congvi_map.nodes[node]['x']) for node in congvi_map.nodes]
    path_coords = [
        [(congvi_map.nodes[e[0]]['y'], congvi_map.nodes[e[0]]['x']), (congvi_map.nodes[e[1]]['y'], congvi_map.nodes[e[1]]['x'])]
        for e in congvi_map.edges
    ]
    return render_template('admin_panel.html', node_coords=node_coords, path_coords=path_coords)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# Cấm đường (admin gọi ajax)
@app.route('/ban_edge', methods=['POST'])
def ban_edge():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    node1_coords = data['node1']
    node2_coords = data['node2']
    direction = data.get('direction', 'both')
    node1 = ox.distance.nearest_nodes(congvi_map, node1_coords[1], node1_coords[0])
    node2 = ox.distance.nearest_nodes(congvi_map, node2_coords[1], node2_coords[0])
    if not congvi_map.has_edge(node1, node2) and not congvi_map.has_edge(node2, node1):
        return jsonify({"error": "Edge not found"}), 404
    if direction == 'both':
        if congvi_map.has_edge(node1, node2):
            congvi_map.remove_edge(node1, node2)
        if congvi_map.has_edge(node2, node1):
            congvi_map.remove_edge(node2, node1)
    elif direction == 'one-way':
        if congvi_map.has_edge(node1, node2):
            congvi_map.remove_edge(node1, node2)
    # Lưu lại đoạn vừa cấm
    banned_edges.append({'node1': node1, 'node2': node2, 'direction': direction})
    global G
    G = Create_simple_Graph(congvi_map)
    return jsonify({"message": "Đã cấm đường thành công!"})

@app.route('/ban_area', methods=['POST'])
def ban_area():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    polygon = data.get('polygon')  # Danh sách [lat, lon]
    if not polygon or len(polygon) < 3:
        return jsonify({"error": "Vùng không hợp lệ"}), 400
    banned_areas.append({'polygon': polygon})
    # Xóa các cạnh nằm trong vùng cấm
    nodes_in_area = []
    for node in congvi_map.nodes:
        y, x = congvi_map.nodes[node]['y'], congvi_map.nodes[node]['x']
        if point_in_polygon((y, x), polygon):
            nodes_in_area.append(node)
    removed_edges = []
    for u, v, k in list(congvi_map.edges(keys=True)):
        if u in nodes_in_area or v in nodes_in_area:
            congvi_map.remove_edge(u, v, key=k)
            removed_edges.append((u, v, k))
    banned_areas[-1]['removed_edges'] = removed_edges  # Lưu lại để khôi phục
    global G
    G = Create_simple_Graph(congvi_map)
    return jsonify({"message": "Đã cấm vùng thành công!"})

@app.route('/restore_last_ban', methods=['POST'])
def restore_last_ban():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    if not banned_edges:
        return jsonify({"error": "Không có đoạn nào để khôi phục!"}), 400
    last = banned_edges.pop()
    node1 = last['node1']
    node2 = last['node2']
    direction = last['direction']
    # Thêm lại edge vào graph
    # Lấy thuộc tính gốc từ file graphml (nếu cần chính xác hơn)
    attrs = {'length': 1}
    if direction == 'both':
        congvi_map.add_edge(node1, node2, **attrs)
        congvi_map.add_edge(node2, node1, **attrs)
    elif direction == 'one-way':
        congvi_map.add_edge(node1, node2, **attrs)
    global G
    G = Create_simple_Graph(congvi_map)
    return jsonify({"message": "Đã khôi phục đoạn vừa cấm!"})

@app.route('/restore_last_ban_area', methods=['POST'])
def restore_last_ban_area():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    if not banned_areas:
        return jsonify({"error": "Không có vùng nào để khôi phục!"}), 400
    last = banned_areas.pop()
    for u, v, k in last.get('removed_edges', []):
        congvi_map.add_edge(u, v, key=k, length=1)
    global G
    G = Create_simple_Graph(congvi_map)
    return jsonify({"message": "Đã khôi phục vùng vừa cấm!"})

algorithm_list = {
    'Dijkstra': Dijkstra, 
    'A Star': A_star, 
    'UCS': UCS,
    'Greedy BFS': Greedy_best_first_search,
}

@app.route('/find_shortest_path', methods=['POST'])
def find_shortest_path():
    data = request.json
    start_coords = data['start']
    end_coords = data['end']
    algorithm = data['algorithm']
    max_depth = int(data['max_depth'])
    start_node = ox.distance.nearest_nodes(congvi_map, start_coords[1], start_coords[0])
    end_node = ox.distance.nearest_nodes(congvi_map, end_coords[1], end_coords[0])
    func = algorithm_list.get(algorithm)
    if not func:
        return jsonify({"error": "Invalid algorithm selected"}), 400
    path_coords = func(G, start_node, end_node)
    start_coords_path =[(congvi_map.nodes[start_node]['y'], congvi_map.nodes[start_node]['x']),(start_coords[0], start_coords[1])]
    end_coords_path =[(congvi_map.nodes[end_node]['y'], congvi_map.nodes[end_node]['x']),(end_coords[0], end_coords[1])]
    if path_coords is None:
        return jsonify({"error": "No path found"}), 404
    return jsonify({'path_coords': path_coords, 'max_depth': max_depth, 'start_path': start_coords_path , 'end_path': end_coords_path })

def point_in_polygon(point, polygon):
    # point: (lat, lon), polygon: [(lat, lon), ...]
    x, y = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n+1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y + 1e-9) + p1x if p2y != p1y else p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside

if __name__ == '__main__':
    print("User interface:  http://localhost:8000/")
    print("Admin login:     http://localhost:8000/admin")
    app.run(debug=True, port=8000)