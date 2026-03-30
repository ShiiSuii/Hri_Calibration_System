import re

with open('/home/ubuntu/TESIS/python_app/node_sequencer.py', 'r') as f:
    code = f.read()

# 1. Add create_rounded_rect helper before class Edge
rounded_helper = """
def create_rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1]
    return canvas.create_polygon(points, **kwargs, smooth=True)

class Edge:
"""
code = code.replace("class Edge:", rounded_helper)

# 2. Modify Node class init for rounded rect and colors
old_color_logic = """        color = "#21262d"
        if node_type == "start": color = "#2ea043"
        elif node_type == "delay": color = "#d29922"
        elif node_type == "action": color = "#1f6feb"
        elif node_type == "tts": color = "#8957e5"
        elif node_type == "stt": color = "#0891b2"
        elif node_type == "camera": color = "#d73a49"
        
        self.rect_id = self.canvas.create_rectangle(x, y, x+width, y+height, fill=color, outline="#30363d", width=2, tags="node")"""

new_color_logic = """        color = "#21262d"
        if node_type == "start": color = "#2ea043"
        elif node_type == "delay": color = "#d29922"
        elif node_type == "action": color = "#1f6feb"
        elif node_type == "tts": color = "#8957e5"
        elif node_type == "stt": color = "#0891b2"
        elif node_type == "camera": color = "#d73a49"
        elif node_type == "stop": color = "#da3633"
        
        self.rect_id = create_rounded_rect(self.canvas, x, y, x+width, y+height, 15, fill=color, outline="#30363d", width=2, tags="node")"""

code = code.replace(old_color_logic, new_color_logic)

# 3. Handle stop port correctly in Node init
old_port_logic = """        if node_type in ["action", "delay", "tts", "stt", "camera"]:
            self.in_port_id = self.canvas.create_oval(x-6, y+height/2-6, x+6, y+height/2+6, fill="#c9d1d9", tags="port")
        if node_type in ["start", "action", "delay", "tts", "stt", "camera"]:
            self.out_port_id = self.canvas.create_oval(x+width-6, y+height/2-6, x+width+6, y+height/2+6, fill="#c9d1d9", tags="port")"""

new_port_logic = """        if node_type in ["action", "delay", "tts", "stt", "camera", "stop"]:
            self.in_port_id = self.canvas.create_oval(x-6, y+height/2-6, x+6, y+height/2+6, fill="#c9d1d9", tags="port")
        if node_type in ["start", "action", "delay", "tts", "stt", "camera"]:
            self.out_port_id = self.canvas.create_oval(x+width-6, y+height/2-6, x+width+6, y+height/2+6, fill="#c9d1d9", tags="port")"""

code = code.replace(old_port_logic, new_port_logic)

# 4. Bind events to update_size
old_widgets_code = """        if node_type == "action":
            actions = [a["name"] for a in self.app.custom_actions]
            if not actions: actions = ["None"]
            self.widget = ctk.CTkOptionMenu(self.app, values=actions, width=120, height=25)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "delay":
            self.widget = ctk.CTkEntry(self.app, width=100, height=25, justify="center")
            self.widget.insert(0, "1.0")
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "tts":
            self.widget = ctk.CTkEntry(self.app, width=140, height=25, justify="center", placeholder_text="Texto a hablar")
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "stt":
            self.widget = ctk.CTkEntry(self.app, width=140, height=25, justify="center", placeholder_text="Palabra a escuchar")
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "camera":
            self.widget = ctk.CTkOptionMenu(self.app, values=["Iniciar Tracking", "Detener Tracking"], width=130, height=25, fg_color="#cb2431", button_color="#b31d28")
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)"""

new_widgets_code = """        if node_type == "action":
            actions = [a["name"] for a in self.app.custom_actions]
            if not actions: actions = ["None"]
            self.widget = ctk.CTkOptionMenu(self.app, values=actions, width=120, height=25, command=self.update_size)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "delay":
            self.widget = ctk.CTkEntry(self.app, width=100, height=25, justify="center")
            self.widget.insert(0, "1.0")
            self.widget.bind("<KeyRelease>", self.update_size)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "tts":
            self.widget = ctk.CTkEntry(self.app, width=140, height=25, justify="center", placeholder_text="Texto a hablar")
            self.widget.bind("<KeyRelease>", self.update_size)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "stt":
            self.widget = ctk.CTkEntry(self.app, width=140, height=25, justify="center", placeholder_text="Palabra a escuchar")
            self.widget.bind("<KeyRelease>", self.update_size)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "camera":
            self.widget = ctk.CTkOptionMenu(self.app, values=["Iniciar Tracking", "Detener Tracking"], width=130, height=25, fg_color="#cb2431", button_color="#b31d28", command=self.update_size)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
            
        self.update_size()"""
code = code.replace(old_widgets_code, new_widgets_code)

# 5. Add update_size to Node
update_size_code = """
    def update_size(self, event=None):
        text_len = len(self.name)
        if self.widget:
            try:
                val = self.widget.get()
                text_len = max(text_len, len(str(val)))
            except:
                pass
                
        new_width = max(160, text_len * 9 + 40)
        
        if new_width != self.width:
            self.width = new_width
            x1, y1, x2, y2 = self.x, self.y, self.x + self.width, self.y + self.height
            r = 15
            points = [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1]
            self.canvas.coords(self.rect_id, points)
            
            self.canvas.coords(self.text_id, self.x + self.width/2, self.y + 15)
            
            if self.widget_window_id:
                self.canvas.coords(self.widget_window_id, self.x + self.width/2, self.y + 50)
                if isinstance(self.widget, ctk.CTkEntry) or isinstance(self.widget, ctk.CTkOptionMenu):
                    self.widget.configure(width=self.width - 40)
                
            if self.out_port_id:
                self.canvas.coords(self.out_port_id, self.x + self.width - 6, self.y + self.height/2 - 6, self.x + self.width + 6, self.y + self.height/2 + 6)
                
            if self.in_edge: self.in_edge.update_positions()
            for e in self.out_edges: e.update_positions()

    def on_press"""

code = code.replace("    def on_press", update_size_code)

# 6. Add Node Stop button
old_buttons = """        ctk.CTkButton(sidebar, text="+ Nodo Cámara", fg_color="#d73a49", hover_color="#cb2431", command=lambda: self.add_node("camera")).pack(pady=5, fill="x")"""
new_buttons = """        ctk.CTkButton(sidebar, text="+ Nodo Cámara", fg_color="#d73a49", hover_color="#cb2431", command=lambda: self.add_node("camera")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Stop", fg_color="#da3633", hover_color="#f85149", command=lambda: self.add_node("stop")).pack(pady=5, fill="x")"""
code = code.replace(old_buttons, new_buttons)

# 7. Add Diagram Saving UI
old_diagram_ui = """        self.status_lbl = ctk.CTkLabel(sidebar, text="Esperando...", text_color="#f2cc60", wraplength=180)
        self.status_lbl.pack(side="bottom", pady=20)"""
new_diagram_ui = """        self.status_lbl = ctk.CTkLabel(sidebar, text="Esperando...", text_color="#f2cc60", wraplength=180)
        self.status_lbl.pack(side="bottom", pady=20)
        
        ctk.CTkLabel(sidebar, text="--- Diagramas ---").pack(pady=10)
        self.diagram_var = ctk.StringVar(value="Seleccionar...")
        self.diagram_menu = ctk.CTkOptionMenu(sidebar, variable=self.diagram_var, values=["Seleccionar..."])
        self.diagram_menu.pack(pady=5, fill="x")
        
        ctk.CTkButton(sidebar, text="Cargar", fg_color="#1f6feb", hover_color="#388bfd", command=self.load_diagram).pack(pady=2, fill="x")
        ctk.CTkButton(sidebar, text="Guardar", fg_color="#2ea043", hover_color="#238636", command=self.save_diagram).pack(pady=2, fill="x")
        ctk.CTkButton(sidebar, text="Eliminar", fg_color="#da3633", hover_color="#f85149", command=self.delete_diagram).pack(pady=2, fill="x")
        
        # self.load_diagram_list() # called after build_ui
"""
code = code.replace(old_diagram_ui, new_diagram_ui)

# 8. Modify add_node signature
old_add_node = """    def add_node(self, node_type):
        name = "Start"
        if node_type == "action": name = "Acción"
        if node_type == "delay": name = "Delay"
        if node_type == "tts": name = "Hablar (TTS)"
        if node_type == "stt": name = "Escuchar (STT)"
        if node_type == "camera": name = "Cámara HRI"
        
        node = Node(self, self.canvas, 50, 50, name, node_type)
        self.nodes.append(node)"""
new_add_node = """    def add_node(self, node_type, x=50, y=50):
        name = "Start"
        if node_type == "action": name = "Acción"
        if node_type == "delay": name = "Delay"
        if node_type == "tts": name = "Hablar (TTS)"
        if node_type == "stt": name = "Escuchar (STT)"
        if node_type == "camera": name = "Cámara HRI"
        if node_type == "stop": name = "Stop / Fin"
        
        node = Node(self, self.canvas, x, y, name, node_type)
        self.nodes.append(node)
        return node"""
code = code.replace(old_add_node, new_add_node)

# 9. Handle stop node execution
old_cam_exec = """            else: # Detener Tracking
                self.stop_camera_tracking()
                self.send_raw_command("L1 R0 G0 B255\\n") # Volver a azul
                self.after(0, finish_node)"""
new_cam_exec = """            else: # Detener Tracking
                self.stop_camera_tracking()
                self.send_raw_command("L1 R0 G0 B255\\n") # Volver a azul
                self.after(0, finish_node)

        elif node.node_type == "stop":
            self.stop_sequence()"""
code = code.replace(old_cam_exec, new_cam_exec)

# 10. Add Diagram logic
diagram_methods = """
    def get_diagrams_file(self):
        return "dialogs.json"
        
    def load_diagram_list(self):
        try:
            if os.path.exists(self.get_diagrams_file()):
                with open(self.get_diagrams_file(), "r") as f:
                    data = json.load(f)
                    names = list(data.keys())
                    if names:
                        self.diagram_menu.configure(values=names)
                        self.diagram_var.set(names[0])
                    else:
                        self.diagram_menu.configure(values=["Seleccionar..."])
                        self.diagram_var.set("Seleccionar...")
        except BaseException as e:
            print("Error parsing dialogs:", e)

    def save_diagram(self):
        dialog = ctk.CTkInputDialog(text="Nombre del diagrama:", title="Guardar Diagrama")
        name = dialog.get_input()
        if not name: return
        
        data = {}
        if os.path.exists(self.get_diagrams_file()):
            try:
                with open(self.get_diagrams_file(), "r") as f:
                    data = json.load(f)
            except BaseException: pass
            
        nodes_data = []
        node_to_idx = {n: i for i, n in enumerate(self.nodes)}
        for n in self.nodes:
            nd = {
                "type": n.node_type,
                "x": n.x,
                "y": n.y,
                "widget_value": n.widget.get() if n.widget else None
            }
            nodes_data.append(nd)
            
        edges_data = []
        for e in self.edges:
            if e.source_node in node_to_idx and e.target_node in node_to_idx:
                edges_data.append({
                    "source": node_to_idx[e.source_node],
                    "target": node_to_idx[e.target_node]
                })
            
        data[name] = {"nodes": nodes_data, "edges": edges_data}
        with open(self.get_diagrams_file(), "w") as f:
            json.dump(data, f, indent=4)
        self.load_diagram_list()
        self.diagram_var.set(name)

    def load_diagram(self):
        name = self.diagram_var.get()
        if name == "Seleccionar..." or not name: return
        
        try:
            with open(self.get_diagrams_file(), "r") as f:
                data = json.load(f)
            if name not in data: return
            
            self.clear_canvas()
            diagram = data[name]
            
            # Create nodes
            for nd in diagram.get("nodes", []):
                n = self.add_node(nd["type"], nd["x"], nd["y"])
                if nd.get("widget_value") is not None and n.widget:
                    if isinstance(n.widget, ctk.CTkEntry):
                        n.widget.delete(0, "end")
                        n.widget.insert(0, nd["widget_value"])
                    elif isinstance(n.widget, ctk.CTkOptionMenu):
                        n.widget.set(nd["widget_value"])
                n.update_size()
                
            # Create edges
            for ed in diagram.get("edges", []):
                s_idx = ed["source"]
                t_idx = ed["target"]
                if s_idx < len(self.nodes) and t_idx < len(self.nodes):
                    s_node = self.nodes[s_idx]
                    t_node = self.nodes[t_idx]
                    
                    edge = Edge(self.canvas, s_node, "out", t_node, "in")
                    self.edges.append(edge)
                    s_node.out_edges.append(edge)
                    t_node.in_edge = edge
        except BaseException as e:
            print("Error cargando diagrama:", e)

    def delete_diagram(self):
        name = self.diagram_var.get()
        if name == "Seleccionar..." or not name: return
        
        try:
            with open(self.get_diagrams_file(), "r") as f:
                data = json.load(f)
            if name in data:
                del data[name]
                with open(self.get_diagrams_file(), "w") as f:
                    json.dump(data, f, indent=4)
                self.load_diagram_list()
        except BaseException:
            pass
"""
# Insert diagram methods right before on_closing
code = code.replace("    def on_closing(self):", diagram_methods + "\n    def on_closing(self):")

# Finally add load_diagram_list() call in __init__
old_init = """        self.load_config()
        self.build_ui()
        self.auto_connect_serial()"""
new_init = """        self.load_config()
        self.build_ui()
        self.load_diagram_list()
        self.auto_connect_serial()"""
code = code.replace(old_init, new_init)

with open('/home/ubuntu/TESIS/python_app/node_sequencer.py', 'w') as f:
    f.write(code)

print("Done.")
