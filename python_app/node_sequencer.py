import customtkinter as ctk
import tkinter as tk
import json
import os
import serial
import serial.tools.list_ports

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"

class Edge:
    def __init__(self, canvas, source_node, source_port, target_node, target_port):
        self.canvas = canvas
        self.source_node = source_node
        self.source_port = source_port
        self.target_node = target_node
        self.target_port = target_port
        self.line_id = self.canvas.create_line(0, 0, 0, 0, smooth=True, width=3, fill="#58a6ff")
        self.update_positions()

    def update_positions(self):
        sx, sy = self.source_node.get_port_coords(self.source_port)
        tx, ty = self.target_node.get_port_coords(self.target_port)
        
        # Calculate spline points
        ctrl1_x, ctrl1_y = sx + 50, sy
        ctrl2_x, ctrl2_y = tx - 50, ty
        
        self.canvas.coords(self.line_id, sx, sy, ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, tx, ty)

    def delete(self):
        self.canvas.delete(self.line_id)

class Node:
    def __init__(self, app, canvas, x, y, name, node_type, width=160, height=80):
        self.app = app
        self.canvas = canvas
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.name = name
        self.node_type = node_type # "start", "action", "delay"
        
        self.in_edge = None
        self.out_edge = None
        
        color = "#21262d"
        if node_type == "start": color = "#2ea043"
        elif node_type == "delay": color = "#d29922"
        elif node_type == "action": color = "#1f6feb"
        
        self.rect_id = self.canvas.create_rectangle(x, y, x+width, y+height, fill=color, outline="#30363d", width=2, tags="node")
        self.text_id = self.canvas.create_text(x+width/2, y+15, text=name, fill="white", font=("Arial", 12, "bold"), tags="node")
        
        # Ports
        self.in_port_id = None
        self.out_port_id = None
        
        if node_type in ["action", "delay"]:
            self.in_port_id = self.canvas.create_oval(x-6, y+height/2-6, x+6, y+height/2+6, fill="#c9d1d9", tags="port")
        if node_type in ["start", "action", "delay"]:
            self.out_port_id = self.canvas.create_oval(x+width-6, y+height/2-6, x+width+6, y+height/2+6, fill="#c9d1d9", tags="port")
            
        # Widgets
        self.widget_window_id = None
        self.widget = None
        
        if node_type == "action":
            actions = [a["name"] for a in self.app.custom_actions]
            if not actions: actions = ["None"]
            self.widget = ctk.CTkOptionMenu(self.app, values=actions, width=120, height=25)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "delay":
            self.widget = ctk.CTkEntry(self.app, width=100, height=25, justify="center")
            self.widget.insert(0, "1.0")
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
            
        self.canvas.tag_bind(self.rect_id, "<ButtonPress-1>", self.on_press)
        self.canvas.tag_bind(self.text_id, "<ButtonPress-1>", self.on_press)
        self.canvas.tag_bind(self.rect_id, "<B1-Motion>", self.on_drag)
        self.canvas.tag_bind(self.text_id, "<B1-Motion>", self.on_drag)
        
        if self.out_port_id:
            self.canvas.tag_bind(self.out_port_id, "<ButtonPress-1>", self.on_port_press)
            self.canvas.tag_bind(self.out_port_id, "<B1-Motion>", self.on_port_drag)
            self.canvas.tag_bind(self.out_port_id, "<ButtonRelease-1>", self.on_port_release)
            
        if self.in_port_id:
            self.canvas.tag_bind(self.in_port_id, "<ButtonRelease-1>", self.on_in_port_release)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def on_drag(self, event):
        dx = event.x - self.start_x
        dy = event.y - self.start_y
        
        self.x += dx
        self.y += dy
        
        self.canvas.move(self.rect_id, dx, dy)
        self.canvas.move(self.text_id, dx, dy)
        if self.in_port_id: self.canvas.move(self.in_port_id, dx, dy)
        if self.out_port_id: self.canvas.move(self.out_port_id, dx, dy)
        if self.widget_window_id:
            coords = self.canvas.coords(self.widget_window_id)
            self.canvas.coords(self.widget_window_id, coords[0]+dx, coords[1]+dy)
            
        if self.in_edge: self.in_edge.update_positions()
        if self.out_edge: self.out_edge.update_positions()
        
        self.start_x = event.x
        self.start_y = event.y

    def on_port_press(self, event):
        self.app.start_edge(self, "out", event.x, event.y)

    def on_port_drag(self, event):
        self.app.drag_edge(event.x, event.y)

    def on_port_release(self, event):
        self.app.end_edge(event.x, event.y)

    def on_in_port_release(self, event):
        self.app.end_edge_on_port(self)

    def get_port_coords(self, port_type):
        if port_type == "in" and self.in_port_id:
            coords = self.canvas.coords(self.in_port_id)
            return (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
        elif port_type == "out" and self.out_port_id:
            coords = self.canvas.coords(self.out_port_id)
            return (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
        return self.x, self.y

class NodeSequencerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Secuenciador Basado en Nodos")
        self.geometry("1000x800")
        
        self.custom_actions = []
        self.servos = []
        
        self.nodes = []
        self.edges = []
        
        self.drawing_edge_id = None
        self.drawing_source_node = None
        
        self.serial_port = None
        self.running = True
        self.seq_running = False
        self.current_execution_node = None
        
        self.load_config()
        self.build_ui()
        self.auto_connect_serial()
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.servos = data
                        self.custom_actions = []
                    else:
                        self.servos = data.get("servos", [])
                        self.custom_actions = data.get("custom_actions", [])
            except Exception:
                pass
                
    def auto_connect_serial(self):
        ports = list(serial.tools.list_ports.comports())
        arduino_port = None
        for p in ports:
            if "Arduino" in p.description or "ACM" in p.device or "USB" in p.device:
                arduino_port = p.device
                break
        
        if not arduino_port and len(ports) > 0:
            arduino_port = ports[0].device
            
        if arduino_port:
            try:
                self.serial_port = serial.Serial(arduino_port, 115200, timeout=1)
                print(f"Conectado a {arduino_port}")
                self.status_lbl.configure(text=f"Conectado a {arduino_port}", text_color="#2ea043")
            except Exception as e:
                print(f"Error al conectar: {e}")
                self.status_lbl.configure(text=f"Error Serial: {e}", text_color="#f85149")
        else:
            self.status_lbl.configure(text="No se encontró Arduino", text_color="#f85149")

    def build_ui(self):
        # Sidebar
        sidebar = ctk.CTkFrame(self, width=200)
        sidebar.pack(side="left", fill="y", padx=10, pady=10)
        
        ctk.CTkLabel(sidebar, text="Herramientas", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        ctk.CTkButton(sidebar, text="+ Nodo Inicio", fg_color="#2ea043", hover_color="#238636", command=lambda: self.add_node("start")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Acción", fg_color="#1f6feb", hover_color="#388bfd", command=lambda: self.add_node("action")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Delay", fg_color="#d29922", hover_color="#e3b341", command=lambda: self.add_node("delay")).pack(pady=5, fill="x")
        
        ctk.CTkLabel(sidebar, text="-------------------").pack(pady=10)
        
        ctk.CTkButton(sidebar, text="▶ Ejecutar Secuencia", fg_color="#238636", hover_color="#2ea043", command=self.play_sequence).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="⏹ Detener", fg_color="#da3633", hover_color="#f85149", command=self.stop_sequence).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="🗑 Limpiar Todo", fg_color="#30363d", hover_color="#4b5563", command=self.clear_canvas).pack(pady=5, fill="x")
        
        self.status_lbl = ctk.CTkLabel(sidebar, text="Esperando...", text_color="#f2cc60", wraplength=180)
        self.status_lbl.pack(side="bottom", pady=20)
        
        # Main Canvas area
        canvas_bg = "#0d1117"
        self.canvas_frame = ctk.CTkFrame(self)
        self.canvas_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg=canvas_bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def add_node(self, node_type):
        name = "Start"
        if node_type == "action": name = "Acción"
        if node_type == "delay": name = "Delay"
        
        node = Node(self, self.canvas, 50, 50, name, node_type)
        self.nodes.append(node)

    def start_edge(self, node, port_type, x, y):
        self.drawing_source_node = node
        # Eliminar cable existente en este puerto out si lo hubiera
        if node.out_edge:
            node.out_edge.delete()
            if node.out_edge in self.edges: self.edges.remove(node.out_edge)
            if node.out_edge.target_node: node.out_edge.target_node.in_edge = None
            node.out_edge = None
            
        self.drawing_edge_id = self.canvas.create_line(x, y, x, y, smooth=True, width=3, fill="#58a6ff", dash=(4, 4))

    def drag_edge(self, x, y):
        if self.drawing_edge_id and self.drawing_source_node:
            sx, sy = self.drawing_source_node.get_port_coords("out")
            ctrl1_x, ctrl1_y = sx + 50, sy
            ctrl2_x, ctrl2_y = x - 50, y
            self.canvas.coords(self.drawing_edge_id, sx, sy, ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, x, y)

    def end_edge(self, x, y):
        # Si soltó en vacío, eliminar
        if self.drawing_edge_id:
            self.canvas.delete(self.drawing_edge_id)
            self.drawing_edge_id = None
        self.drawing_source_node = None

    def end_edge_on_port(self, target_node):
        if self.drawing_edge_id and self.drawing_source_node:
            # Eliminar edge de dibujo
            self.canvas.delete(self.drawing_edge_id)
            self.drawing_edge_id = None
            
            # Impedir auto-conexion
            if target_node == self.drawing_source_node: return
            
            # Quitar cable anterior de destino si lo hubiera
            if target_node.in_edge:
                target_node.in_edge.delete()
                if target_node.in_edge in self.edges: self.edges.remove(target_node.in_edge)
                if target_node.in_edge.source_node: target_node.in_edge.source_node.out_edge = None
                
            edge = Edge(self.canvas, self.drawing_source_node, "out", target_node, "in")
            self.edges.append(edge)
            
            self.drawing_source_node.out_edge = edge
            target_node.in_edge = edge
            self.drawing_source_node = None

    def clear_canvas(self):
        for e in self.edges:
            e.delete()
        self.edges.clear()
        
        for n in self.nodes:
            if n.widget_window_id: self.canvas.delete(n.widget_window_id)
            self.canvas.delete(n.rect_id)
            self.canvas.delete(n.text_id)
            if n.in_port_id: self.canvas.delete(n.in_port_id)
            if n.out_port_id: self.canvas.delete(n.out_port_id)
            if n.widget: n.widget.destroy()
        self.nodes.clear()

    # ==========================
    # Sequence Execution Engine
    # ==========================
    
    def send_raw_command(self, cmd):
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            try:
                self.serial_port.write(cmd.encode())
            except:
                pass

    def send_command(self, channel, pulse):
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            cmd = f"C{channel} P{pulse}\n"
            try:
                self.serial_port.write(cmd.encode())
            except:
                pass

    def execute_action(self, action_name):
        cfg_str = ""
        for act in self.custom_actions:
            if act["name"] == action_name:
                cfg_str = act.get("config", "")
                break
                
        if not cfg_str: return
        
        moves = []
        try:
            parts = cfg_str.split(",")
            for p in parts:
                if ":" in p:
                    ch, pulse = p.split(":")
                    if pulse.strip().upper() == "M":
                        pulse_val = 375 # valor por defecto de mid
                        for s in self.servos:
                            if s["id"] == int(ch.strip()):
                                pulse_val = s.get("mid", 375)
                    else:
                        pulse_val = int(pulse.strip())
                    moves.append((int(ch.strip()), pulse_val))
        except Exception:
            return
            
        for ch, pulse in moves:
            self.send_command(ch, pulse)
            
        # Apagar servos después de un tiempo para evitar sobrecalentamiento
        def turn_off():
            for ch, _ in moves:
                self.send_command(ch, 0)
        self.after(500, turn_off)

    def highlight_node(self, node):
        for n in self.nodes:
            color = "#21262d"
            if n.node_type == "start": color = "#2ea043"
            elif n.node_type == "delay": color = "#d29922"
            elif n.node_type == "action": color = "#1f6feb"
            self.canvas.itemconfig(n.rect_id, width=2, outline="#30363d")
            
        if node:
            self.canvas.itemconfig(node.rect_id, outline="#f2cc60", width=4)

    def play_sequence(self):
        if self.seq_running: return
        
        start_nodes = [n for n in self.nodes if n.node_type == "start"]
        if not start_nodes:
            self.status_lbl.configure(text="No hay nodo Start!", text_color="#f85149")
            return
            
        self.seq_running = True
        self.status_lbl.configure(text="Secuencia Ejecutando...", text_color="#2ea043")
        self.current_execution_node = start_nodes[0]
        self.run_node()

    def stop_sequence(self):
        self.seq_running = False
        self.highlight_node(None)
        self.status_lbl.configure(text="Secuencia Detenida", text_color="#f2cc60")

    def run_node(self):
        if not self.seq_running or not self.current_execution_node:
            self.stop_sequence()
            return
            
        node = self.current_execution_node
        self.highlight_node(node)
        
        delay_ms = 50 # minimal delay between pure computation
        
        if node.node_type == "action":
            act_name = node.widget.get()
            self.execute_action(act_name)
            delay_ms = 100 # Esperar que el motor reciba antes del siguiente
        elif node.node_type == "delay":
            try:
                val = float(node.widget.get())
                delay_ms = int(val * 1000)
            except:
                delay_ms = 1000
                
        # Buscar el siguiente nodo a traves del edge de salida
        next_node = None
        if node.out_edge and node.out_edge.target_node:
            next_node = node.out_edge.target_node
            
        self.current_execution_node = next_node
        self.after(delay_ms, self.run_node)

    def on_closing(self):
        self.running = False
        self.seq_running = False
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            try:
                self.serial_port.close()
            except:
                pass
        self.destroy()

if __name__ == "__main__":
    app = NodeSequencerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
