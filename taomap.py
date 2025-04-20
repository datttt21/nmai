import osmnx as ox

# Tải bản đồ khu vực Cống Vị
place_name = "Cống Vị, Ba Đình, Hà Nội, Việt Nam"
G = ox.graph_from_place(place_name, network_type="walk")

# Lưu lại file graphml để sử dụng sau này
ox.save_graphml(G, "congvi_badinh_hanoi_graph.graphml")

print("1")
