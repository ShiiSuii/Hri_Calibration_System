import customtkinter as ctk
import tkinter as tk
import json
import os
import serial
import serial.tools.list_ports
import threading
import pyttsx3
import speech_recognition as sr
import cv2
import csv
import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"


def create_rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1]
    return canvas.create_polygon(points, **kwargs, smooth=True)

class Edge:

    def __init__(self, canvas, source_node, source_port, target_node, target_port):
        self.canvas = canvas
        self.source_node = source_node
        self.source_port = source_port
        self.target_node = target_node
        self.target_port = target_port
        self.line_id = self.canvas.create_line(0, 0, 0, 0, smooth=True, width=3, fill="#58a6ff")
        self.update_positions()
        
        # Bind right-click to delete
        self.canvas.tag_bind(self.line_id, "<Button-3>", self.on_right_click)

    def on_right_click(self, event):
        self.delete()

    def update_positions(self):
        sx, sy = self.source_node.get_port_coords(self.source_port)
        tx, ty = self.target_node.get_port_coords(self.target_port)
        
        # Calculate spline points
        ctrl1_x, ctrl1_y = sx + 50, sy
        ctrl2_x, ctrl2_y = tx - 50, ty
        
        self.canvas.coords(self.line_id, sx, sy, ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, tx, ty)

    def delete(self):
        self.canvas.delete(self.line_id)
        # Cleanup references in nodes
        if self in self.source_node.out_edges:
            self.source_node.out_edges.remove(self)
        if self.target_node.in_edge == self:
            self.target_node.in_edge = None
        # Cleanup in app
        if hasattr(self.source_node.app, 'edges') and self in self.source_node.app.edges:
            self.source_node.app.edges.remove(self)

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
        self.out_edges = []
        
        color = "#21262d"
        if node_type == "start": color = "#2ea043"
        elif node_type == "delay": color = "#d29922"
        elif node_type == "action": color = "#1f6feb"
        elif node_type == "tts": color = "#8957e5"
        elif node_type == "stt": color = "#0891b2"
        elif node_type == "camera": color = "#d73a49"
        elif node_type == "blink": color = "#ff7b72"
        elif node_type == "jaw": color = "#f78166"
        elif node_type == "stop": color = "#da3633"
        elif node_type == "led": color = "#39c5bb"
        
        self.rect_id = create_rounded_rect(self.canvas, x, y, x+width, y+height, 15, fill=color, outline="#30363d", width=2, tags="node")
        self.text_id = self.canvas.create_text(x+width/2, y+15, text=name, fill="white", font=("Arial", 12, "bold"), tags="node")
        
        # Ports
        self.in_port_id = None
        self.out_port_id = None
        
        if node_type in ["action", "delay", "tts", "stt", "camera", "stop", "blink", "jaw", "led"]:
            self.in_port_id = self.canvas.create_oval(x-10, y+height/2-10, x+10, y+height/2+10, fill="#c9d1d9", outline="#8b949e", width=2, tags="port")
        if node_type in ["start", "action", "delay", "tts", "stt", "camera", "blink", "jaw", "led"]:
            self.out_port_id = self.canvas.create_oval(x+width-10, y+height/2-10, x+width+10, y+height/2+10, fill="#c9d1d9", outline="#8b949e", width=2, tags="port")
            
        # Widgets
        self.widget_window_id = None
        self.widget = None
        
        if node_type == "action":
            actions = [a["name"] for a in self.app.custom_actions]
            if "Parpadear" not in actions:
                actions.append("Parpadear")
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
            self.widget = ctk.CTkEntry(self.app, width=140, height=25, justify="center", placeholder_text="Pregunta Inicial")
            self.widget.insert(0, "Hola, ¿Cómo te llamas?")
            self.widget.bind("<KeyRelease>", self.update_size)
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget)
        elif node_type == "blink":
            self.widget_frame = ctk.CTkFrame(self.app, fg_color="transparent")
            self.repeat_entry = ctk.CTkEntry(self.widget_frame, width=40, height=25, justify="center")
            self.repeat_entry.insert(0, "3")
            self.repeat_entry.bind("<KeyRelease>", self.update_size)
            self.repeat_entry.pack(side="left", padx=2)
            
            # Speed slider: 0.05 (fast) to 0.8 (slow)
            self.speed_slider = ctk.CTkSlider(self.widget_frame, from_=0.05, to=0.8, width=80, height=20, number_of_steps=15, command=self.update_size)
            self.speed_slider.set(0.3)
            self.speed_slider.pack(side="left", padx=2)
            
            self.widget = self.widget_frame
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget_frame)
        elif node_type == "jaw":
            self.widget_frame = ctk.CTkFrame(self.app, fg_color="transparent")
            self.routine_type = ctk.CTkOptionMenu(self.widget_frame, values=["Simple", "Conversación"], width=100, height=25, command=self.update_size)
            self.routine_type.pack(side="left", padx=2)
            self.repeat_entry = ctk.CTkEntry(self.widget_frame, width=40, height=25, justify="center")
            self.repeat_entry.insert(0, "3")
            self.repeat_entry.bind("<KeyRelease>", self.update_size)
            self.repeat_entry.pack(side="left", padx=2)
            # Speed slider: 0.1 (fast) to 1.0 (slow)
            self.speed_slider = ctk.CTkSlider(self.widget_frame, from_=0.1, to=1.0, width=80, height=20, number_of_steps=18, command=self.update_size)
            self.speed_slider.set(0.4)
            self.speed_slider.pack(side="left", padx=2)
            self.widget = self.widget_frame
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget_frame)
        elif node_type == "led":
            self.widget_frame = ctk.CTkFrame(self.app, fg_color="transparent")
            self.led_num = ctk.CTkOptionMenu(self.widget_frame, values=["LED 1", "LED 2", "Ambos"], width=80, height=25, command=self.update_size)
            self.led_num.pack(side="left", padx=2)
            self.led_color = ctk.CTkOptionMenu(self.widget_frame, values=["Rojo", "Verde", "Azul", "Cian", "Apagar"], width=90, height=25, command=self.update_size)
            self.led_color.pack(side="left", padx=2)
            self.widget = self.widget_frame
            self.widget_window_id = self.canvas.create_window(x+width/2, y+50, window=self.widget_frame)
            
        self.update_size()
            
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

        # Botón de borrado
        self.delete_btn_id = self.canvas.create_text(x+width-15, y+15, text="✖", fill="#f85149", font=("Arial", 14, "bold"), tags="node")
        self.canvas.tag_bind(self.delete_btn_id, "<ButtonPress-1>", self.on_delete_press)

    def on_delete_press(self, event):
        self.app.delete_node(self)

    def update_size(self, event=None):
        text_len = len(self.name)
        if self.widget:
            try:
                if self.node_type == "jaw":
                    val = self.routine_type.get() + self.repeat_entry.get()
                elif self.node_type == "blink":
                    val = self.repeat_entry.get() + "Speed" # Dummy for width
                elif self.node_type == "led":
                    val = self.led_num.get() + self.led_color.get()
                else:
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
                if self.node_type not in ["jaw", "blink", "led"]:
                    if isinstance(self.widget, ctk.CTkEntry) or isinstance(self.widget, ctk.CTkOptionMenu):
                        self.widget.configure(width=self.width - 40)
                
            if self.out_port_id:
                self.canvas.coords(self.out_port_id, self.x + self.width - 10, self.y + self.height/2 - 10, self.x + self.width + 10, self.y + self.height/2 + 10)
                
            if hasattr(self, 'delete_btn_id'):
                self.canvas.coords(self.delete_btn_id, self.x + self.width - 15, self.y + 15)
                
            if self.in_edge: self.in_edge.update_positions()
            for e in self.out_edges: e.update_positions()

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
            
        if hasattr(self, 'delete_btn_id'):
            self.canvas.move(self.delete_btn_id, dx, dy)
            
        if self.in_edge: self.in_edge.update_positions()
        for e in self.out_edges: e.update_positions()
        
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
        self.geometry("1200x900")
        
        self.custom_actions = []
        self.servos = []
        
        self.nodes = []
        self.edges = []
        
        self.drawing_edge_id = None
        self.drawing_source_node = None
        
        self.serial_port = None
        self.running = True
        self.seq_running = False
        self.active_nodes = []
        
        self.load_config()
        self.build_ui()
        self.load_diagram_list()
        self.auto_connect_serial()
        
        # Start serial monitor thread
        threading.Thread(target=self.serial_monitor, daemon=True).start()
        
        # Initial Robot State
        self.after(2000, lambda: self.set_robot_state("IDLE"))
        
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

    def set_robot_state(self, state):
        """Gestiona el color del LED 1 según el estado del robot"""
        states = {
            "IDLE": (0, 0, 255),      # Azul (Standby)
            "SPEAKING": (0, 255, 0),   # Verde (Hablando)
            "LISTENING": (255, 255, 0), # Amarillo (Escuchando)
            "THINKING": (255, 0, 255),  # Magenta (Procesando)
            "VISION": (255, 255, 255), # Blanco (Cámara Activa)
            "OFF": (0, 0, 0)
        }
        r, g, b = states.get(state.upper(), (0, 0, 0))
        self.send_raw_command(f"L1 R{r} G{g} B{b}\n")

    def serial_monitor(self):
        while self.running:
            if self.serial_port and getattr(self.serial_port, 'is_open', False):
                try:
                    if self.serial_port.in_waiting > 0:
                        line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            print(f"[Arduino] {line}")
                except Exception:
                    pass
            import time
            time.sleep(0.1)

    def build_ui(self):
        # Sidebar
        sidebar = ctk.CTkScrollableFrame(self, width=220)
        sidebar.pack(side="left", fill="y", padx=10, pady=10)
        
        ctk.CTkLabel(sidebar, text="Herramientas", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        ctk.CTkButton(sidebar, text="+ Nodo Inicio", fg_color="#2ea043", hover_color="#238636", command=lambda: self.add_node("start")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Acción", fg_color="#1f6feb", hover_color="#388bfd", command=lambda: self.add_node("action")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Delay", fg_color="#d29922", hover_color="#e3b341", command=lambda: self.add_node("delay")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Hablar", fg_color="#8957e5", hover_color="#a371f7", command=lambda: self.add_node("tts")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Escuchar", fg_color="#0891b2", hover_color="#06b6d4", command=lambda: self.add_node("stt")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Cámara", fg_color="#d73a49", hover_color="#cb2431", command=lambda: self.add_node("camera")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Parpadear", fg_color="#ff7b72", hover_color="#d73a49", command=lambda: self.add_node("blink")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Mandíbula", fg_color="#f78166", hover_color="#ce5a43", command=lambda: self.add_node("jaw")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo LED RGB", fg_color="#39c5bb", hover_color="#06b6d4", command=lambda: self.add_node("led")).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="+ Nodo Stop", fg_color="#da3633", hover_color="#f85149", command=lambda: self.add_node("stop")).pack(pady=5, fill="x")
        
        ctk.CTkLabel(sidebar, text="--- Opciones de Voz ---").pack(pady=5)
        self.tts_engine_var = ctk.StringVar(value="Natural (gTTS)")
        self.tts_menu = ctk.CTkOptionMenu(sidebar, variable=self.tts_engine_var, values=["Natural (gTTS)", "Robótica (pyttsx3)"])
        self.tts_menu.pack(pady=5, fill="x")
        
        ctk.CTkLabel(sidebar, text="--- Canvas ---").pack(pady=5)
        bg_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        bg_frame.pack(fill="x", pady=2)
        ctk.CTkButton(bg_frame, text="Osc", width=60, height=25, fg_color="#0d1117", hover_color="#161b22", command=lambda: self.change_canvas_bg("Negro")).pack(side="left", padx=2, expand=True)
        ctk.CTkButton(bg_frame, text="Gris", width=60, height=25, fg_color="#333333", hover_color="#444444", command=lambda: self.change_canvas_bg("Gris")).pack(side="left", padx=2, expand=True)
        ctk.CTkButton(bg_frame, text="Claro", width=60, height=25, fg_color="#888888", hover_color="#aaaaaa", command=lambda: self.change_canvas_bg("Blanco")).pack(side="left", padx=2, expand=True)
        
        ctk.CTkLabel(sidebar, text="-------------------").pack(pady=10)
        
        # Data logger toggle
        self.logging_active = False
        self.log_data = []
        self.log_btn = ctk.CTkButton(sidebar, text="Grabar Datos: OFF", fg_color="#30363d", hover_color="#4b5563", command=self.toggle_data_logging)
        self.log_btn.pack(pady=5, fill="x")
        
        ctk.CTkButton(sidebar, text="Ejecutar Secuencia", fg_color="#238636", hover_color="#2ea043", command=self.play_sequence).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="Detener", fg_color="#da3633", hover_color="#f85149", command=self.stop_sequence).pack(pady=5, fill="x")
        ctk.CTkButton(sidebar, text="Limpiar Todo", fg_color="#30363d", hover_color="#4b5563", command=self.clear_canvas).pack(pady=5, fill="x")
        
        self.status_lbl = ctk.CTkLabel(sidebar, text="Esperando...", text_color="#f2cc60", wraplength=180)
        self.status_lbl.pack(side="bottom", pady=20)
        
        ctk.CTkLabel(sidebar, text="--- Diagramas ---").pack(pady=10)
        self.diagram_var = ctk.StringVar(value="Seleccionar...")
        self.diagram_menu = ctk.CTkOptionMenu(sidebar, variable=self.diagram_var, values=["Seleccionar..."])
        self.diagram_menu.pack(pady=5, fill="x")
        
        ctk.CTkButton(sidebar, text="Cargar", fg_color="#1f6feb", hover_color="#388bfd", command=self.load_diagram).pack(pady=2, fill="x")
        ctk.CTkButton(sidebar, text="Guardar", fg_color="#2ea043", hover_color="#238636", command=self.save_diagram).pack(pady=2, fill="x")
        ctk.CTkButton(sidebar, text="Eliminar", fg_color="#da3633", hover_color="#f85149", command=self.delete_diagram).pack(pady=2, fill="x")
        
        # self.load_diagram_list() # called after build_ui

        
        # Main Canvas area
        self.canvas_bg = "#0d1117"
        self.canvas_frame = ctk.CTkFrame(self)
        self.canvas_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg=self.canvas_bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._grid_after_id = None
        self.canvas.bind("<Configure>", self._schedule_grid_redraw)
        self.after(500, self.draw_grid)

    def _schedule_grid_redraw(self, event=None):
        if self._grid_after_id:
            self.after_cancel(self._grid_after_id)
        self._grid_after_id = self.after(200, self.draw_grid)

    def draw_grid(self, event=None):
        self.canvas.delete("grid")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return
        
        bg_colors = {"#0d1117": "#161b22", "#333333": "#444444", "#ffffff": "#e0e0e0"}
        grid_color = bg_colors.get(self.canvas_bg, "#222222")
        
        step = 30
        for x in range(0, w, step):
            self.canvas.create_line(x, 0, x, h, fill=grid_color, tags="grid")
        for y in range(0, h, step):
            self.canvas.create_line(0, y, w, y, fill=grid_color, tags="grid")
        
        self.canvas.tag_lower("grid")

    def change_canvas_bg(self, choice):
        colors = {"Negro": "#0d1117", "Gris": "#333333", "Blanco": "#ffffff"}
        self.canvas_bg = colors.get(choice, "#0d1117")
        self.canvas.configure(bg=self.canvas_bg)
        self.draw_grid()

    def toggle_data_logging(self):
        if self.logging_active:
            # Stop logging and save
            self.logging_active = False
            self.log_btn.configure(text="📊 Grabar Datos: OFF", fg_color="#30363d")
            if self.log_data:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                filename = f"motor_log_{timestamp}.csv"
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "command_type", "target", "value"])
                    writer.writerows(self.log_data)
                print(f"[Logger] Datos guardados en {filename} ({len(self.log_data)} registros)")
                self.status_lbl.configure(text=f"Log guardado: {filename}", text_color="#2ea043")
            self.log_data = []
        else:
            self.logging_active = True
            self.log_data = []
            self.log_btn.configure(text="Grabar Datos: ON", fg_color="#238636")
            self.status_lbl.configure(text="Logger activo...", text_color="#2ea043")


    def add_node(self, node_type, x=50, y=50):
        name = "Start"
        if node_type == "action": name = "Acción"
        if node_type == "delay": name = "Delay"
        if node_type == "tts": name = "Hablar (TTS)"
        if node_type == "stt": name = "Escuchar (STT)"
        if node_type == "camera": name = "Cámara HRI"
        if node_type == "blink": name = "Parpadear"
        if node_type == "jaw": name = "Mandíbula"
        if node_type == "led": name = "Control LED"
        if node_type == "stop": name = "Stop / Fin"
        
        node = Node(self, self.canvas, x, y, name, node_type)
        self.nodes.append(node)
        return node

    def start_edge(self, node, port_type, x, y):
        self.drawing_source_node = node
        self.drawing_edge_id = self.canvas.create_line(x, y, x, y, smooth=True, width=3, fill="#58a6ff", dash=(4, 4))

    def drag_edge(self, x, y):
        if self.drawing_edge_id and self.drawing_source_node:
            sx, sy = self.drawing_source_node.get_port_coords("out")
            ctrl1_x, ctrl1_y = sx + 50, sy
            ctrl2_x, ctrl2_y = x - 50, y
            self.canvas.coords(self.drawing_edge_id, sx, sy, ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, x, y)

    def end_edge(self, x, y):
        if not self.drawing_source_node:
            # Limpiar si es necesario
            if self.drawing_edge_id:
                self.canvas.delete(self.drawing_edge_id)
                self.drawing_edge_id = None
            return

        overlapping = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)
        connected = False
        
        for n in self.nodes:
            if n.in_port_id and n.in_port_id in overlapping:
                # Se soltó sobre un puerto de entrada (in)
                target_node = n
                # Impedir auto-conexion
                if target_node == self.drawing_source_node: continue
                
                # Quitar cable anterior de destino si lo hubiera
                if target_node.in_edge:
                    target_node.in_edge.delete()
                    if target_node.in_edge in self.edges: self.edges.remove(target_node.in_edge)
                    if target_node.in_edge.source_node:
                        if target_node.in_edge in target_node.in_edge.source_node.out_edges:
                            target_node.in_edge.source_node.out_edges.remove(target_node.in_edge)
                
                edge = Edge(self.canvas, self.drawing_source_node, "out", target_node, "in")
                self.edges.append(edge)
                
                self.drawing_source_node.out_edges.append(edge)
                target_node.in_edge = edge
                connected = True
                break
                
        # Si soltó en vacío, eliminar
        if self.drawing_edge_id:
            self.canvas.delete(self.drawing_edge_id)
            self.drawing_edge_id = None
        self.drawing_source_node = None

    def end_edge_on_port(self, target_node):
        pass # Obsoleto, la logica fue traspasada a end_edge

    def delete_node(self, node):
        if node in self.nodes:
            self.nodes.remove(node)
            
        edges_to_remove = []
        for e in self.edges:
            if e.source_node == node or e.target_node == node:
                edges_to_remove.append(e)
                
        for e in edges_to_remove:
            e.delete()
            if e in self.edges:
                self.edges.remove(e)
            if e.source_node and e in e.source_node.out_edges:
                e.source_node.out_edges.remove(e)
            if e.target_node and e.target_node.in_edge == e:
                e.target_node.in_edge = None
                
        if node in self.active_nodes:
            self.active_nodes.remove(node)
            
        if node.widget_window_id: self.canvas.delete(node.widget_window_id)
        if hasattr(node, "delete_btn_id") and node.delete_btn_id: self.canvas.delete(node.delete_btn_id)
        self.canvas.delete(node.rect_id)
        self.canvas.delete(node.text_id)
        if node.in_port_id: self.canvas.delete(node.in_port_id)
        if node.out_port_id: self.canvas.delete(node.out_port_id)
        if node.widget: node.widget.destroy()

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
                if self.logging_active:
                    self.log_data.append([datetime.datetime.now().isoformat(), "raw", cmd.strip(), ""])
            except:
                pass

    def send_command(self, channel, pulse):
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            cmd = f"C{channel} P{pulse}\n"
            try:
                self.serial_port.write(cmd.encode())
                if self.logging_active:
                    self.log_data.append([datetime.datetime.now().isoformat(), "servo", str(channel), str(pulse)])
            except:
                pass

    def execute_action(self, action_name):
        if action_name == "Parpadear":
            self.blink_eyes(times=2) # Default for quick action
            return
            
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

    def blink_eyes(self, times=3, speed=0.3, finish_callback=None):
        def blink_routine(count):
            if not self.seq_running and count > 0: return 
            
            if count < times:
                self.execute_action("OJOS CERRADOS")
                def open_eyes():
                    self.execute_action("OJOS ABIERTOS")
                    # Speed controls the delay between cycles and within cycles
                    self.after(int(speed * 1000), lambda: blink_routine(count + 1))
                self.after(int(speed * 0.7 * 1000), open_eyes)
            else:
                if finish_callback:
                    self.after(0, finish_callback)
        
        blink_routine(0)
        
    def jaw_routine(self, times=3, routine_type="Simple", speed=0.4, finish_callback=None):
        def routine_step(count):
            if not self.seq_running and count > 0: return
            
            if count < times:
                if routine_type == "Simple":
                    self.execute_action("Cr\u00e1neo: Abrir Mand\u00edbula")
                    def close_simple():
                        self.execute_action("Cr\u00e1neo: Cerrar Mand\u00edbula")
                        self.after(int(speed * 1000), lambda: routine_step(count + 1))
                    self.after(int(speed * 1000), close_simple)
                else: # Conversación
                    # Abrir -> Cerrar -> Mitad -> Cerrar -> Abrir -> Cerrar
                    self.execute_action("Cr\u00e1neo: Abrir Mand\u00edbula")
                    def step2():
                        self.execute_action("Cr\u00e1neo: Cerrar Mand\u00edbula")
                        def step3():
                            self.send_command(0, 315) # Mitad (hardcoded based on config.json mid=315)
                            def step4():
                                self.execute_action("Cr\u00e1neo: Cerrar Mand\u00edbula")
                                def step5():
                                    self.execute_action("Cr\u00e1neo: Abrir Mand\u00edbula")
                                    def step6():
                                        self.execute_action("Cr\u00e1neo: Cerrar Mand\u00edbula")
                                        self.after(max(100, int(speed * 500)), lambda: routine_step(count + 1))
                                    self.after(max(100, int(speed * 500)), step6)
                                self.after(max(100, int(speed * 500)), step5)
                            self.after(max(100, int(speed * 500)), step4)
                        self.after(max(100, int(speed * 500)), step3)
                    self.after(max(100, int(speed * 500)), step2)
            else:
                if finish_callback:
                    self.after(0, finish_callback)
                    
        routine_step(0)

    def start_camera_tracking(self):
        if hasattr(self, 'camera_running') and self.camera_running:
            return
            
        self.camera_running = True
        
        def tracking_thread():
            cap = cv2.VideoCapture(0)
            # Find Haar Cascade
            cascade_path = "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"
            if not os.path.exists(cascade_path):
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            
            face_cascade = cv2.CascadeClassifier(cascade_path)
            
            p18, p19 = 362, 375 # MIDs
            
            while self.camera_running and self.seq_running and self.running:
                ret, frame = cap.read()
                if not ret: break
                
                frame = cv2.flip(frame, 1)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
                
                h, w = frame.shape[:2]
                cx, cy = w // 2, h // 2
                
                if len(faces) > 0:
                    (x, y, fw, fh) = faces[0]
                    fx, fy = x + fw // 2, y + fh // 2
                    
                    # Proportional Tracking
                    err_x, err_y = fx - cx, fy - cy
                    thresh = 30
                    k = 25
                    ms = 8
                    
                    if abs(err_x) > thresh:
                        step_x = min(ms, max(1, int(abs(err_x) / k)))
                        if err_x > 0: p19 -= step_x
                        else: p19 += step_x
                        
                    if abs(err_y) > thresh:
                        step_y = min(ms, max(1, int(abs(err_y) / k)))
                        if err_y > 0: p18 += step_y
                        else: p18 -= step_y
                        
                    p18 = max(200, min(550, p18))
                    p19 = max(150, min(600, p19))
                    
                    self.send_command(18, p18)
                    self.send_command(19, p19)
                
                cv2.imshow('HRI Camera Tracking', frame)
                if cv2.waitKey(10) & 0xFF == ord('q'):
                    break
                    
            cap.release()
            cv2.destroyAllWindows()
            self.send_command(18, 362)
            self.send_command(19, 375)
            
        threading.Thread(target=tracking_thread, daemon=True).start()

    def speak_sync(self, text):
        engine_type = getattr(self, "tts_engine_var", ctk.StringVar(value="Natural")).get()
        if "Natural" in engine_type:
            try:
                from gtts import gTTS
                import pygame
                import tempfile
                
                tts = gTTS(text=text, lang='es')
                temp_file = tempfile.mktemp(suffix=".mp3")
                tts.save(temp_file)
                if not pygame.mixer.get_init(): pygame.mixer.init()
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and self.seq_running:
                    time.sleep(0.1)
                pygame.mixer.music.stop()
                try: os.remove(temp_file)
                except: pass
            except Exception as e:
                print("Error gTTS sync:", e)
                try:
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except: pass
        else:
            try:
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except: pass

    def listen_sync(self, label=""):
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            self.status_lbl.configure(text=f"Escuchando {label}...", text_color="#0891b2")
            try:
                audio = r.listen(source, timeout=5, phrase_time_limit=5)
                recognized = r.recognize_google(audio, language="es-ES")
                return recognized
            except Exception as e:
                print(f"Error STT sync ({label}):", e)
                return None
        
    def stop_camera_tracking(self):
        self.camera_running = False

    def update_highlights(self):
        for n in self.nodes:
            self.canvas.itemconfig(n.rect_id, width=2, outline="#30363d")
        for active in self.active_nodes:
            self.canvas.itemconfig(active.rect_id, outline="#f2cc60", width=4)

    def play_sequence(self):
        if self.seq_running: return
        
        start_nodes = [n for n in self.nodes if n.node_type == "start"]
        if not start_nodes:
            self.status_lbl.configure(text="No hay nodo Start!", text_color="#f85149")
            return
            
        self.seq_running = True
        self.status_lbl.configure(text="Secuencia Ejecutando...", text_color="#2ea043")
        self.set_robot_state("THINKING")
        self.active_nodes = []
        for n in start_nodes:
            self.run_node(n)

    def stop_sequence(self):
        self.seq_running = False
        self.active_nodes = []
        self.update_highlights()
        self.status_lbl.configure(text="Secuencia Detenida", text_color="#f2cc60")
        self.set_robot_state("IDLE")
        if hasattr(self, 'camera_running') and self.camera_running:
            self.stop_camera_tracking()

    def run_node(self, node):
        if not self.seq_running: return
        
        if node not in self.active_nodes:
            self.active_nodes.append(node)
        self.update_highlights()
        
        def finish_node():
            if not self.seq_running: return
            if node in self.active_nodes:
                self.active_nodes.remove(node)
            self.update_highlights()
            for edge in node.out_edges:
                if edge.target_node:
                    self.run_node(edge.target_node)
                    
        if node.node_type == "start":
            self.after(50, finish_node)
            
        elif node.node_type == "action":
            act_name = node.widget.get()
            self.execute_action(act_name)
            self.after(100, finish_node)
            
        elif node.node_type == "delay":
            try:
                val = float(node.widget.get())
                delay_ms = int(val * 1000)
            except:
                delay_ms = 1000
            self.after(delay_ms, finish_node)
            
        elif node.node_type == "tts":
            text = node.widget.get()
            self.set_robot_state("SPEAKING")
            
            def speak_thread():
                engine_type = getattr(self, "tts_engine_var", ctk.StringVar(value="Natural")).get()
                if "Natural" in engine_type:
                    try:
                        from gtts import gTTS
                        import pygame
                        import tempfile
                        
                        tts = gTTS(text=text, lang='es')
                        temp_file = tempfile.mktemp(suffix=".mp3", prefix="hri_tts_")
                        tts.save(temp_file)
                        
                        if not pygame.mixer.get_init():
                            pygame.mixer.init()
                        pygame.mixer.music.load(temp_file)
                        pygame.mixer.music.play()
                        
                        while pygame.mixer.music.get_busy() and self.seq_running:
                            pygame.time.Clock().tick(10)
                            
                        pygame.mixer.music.stop()
                        pygame.mixer.quit()
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    except Exception as e:
                        print("Error gTTS, usando pyttsx3 fallback:", e)
                        try:
                            engine = pyttsx3.init()
                            engine.say(text)
                            engine.runAndWait()
                        except Exception as e2:
                            print("Error pyttsx3 fallback:", e2)
                else:
                    try:
                        engine = pyttsx3.init()
                        engine.say(text)
                        engine.runAndWait()
                    except Exception as e:
                        print("Error pyttsx3:", e)
                        
                if self.seq_running:
                    self.set_robot_state("IDLE")
                    self.after(0, finish_node)
                    
            threading.Thread(target=speak_thread, daemon=True).start()
            
        elif node.node_type == "stt":
            expected_text = node.widget.get().lower().strip()
            self.set_robot_state("LISTENING")
            
            def listen_thread():
                r = sr.Recognizer()
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    while self.seq_running:
                        try:
                            audio = r.listen(source, timeout=3, phrase_time_limit=5)
                            recognized = r.recognize_google(audio, language="es-ES").lower()
                            print("Speech Recognized:", recognized)
                            if expected_text in recognized:
                                break
                        except sr.WaitTimeoutError:
                            continue
                        except Exception as e:
                            # Silently ignore noise/unrecognized
                            continue
                if self.seq_running:
                    self.send_raw_command("L1 R0 G0 B255\n") # Azul (Idle)
                    self.after(0, finish_node)
                    
            if not expected_text:
                # If no text provided, just pass
                self.after(0, finish_node)
            else:
                threading.Thread(target=listen_thread, daemon=True).start()

        elif node.node_type == "camera":
            pregunta = node.widget.get() or "Hola, ¿Cómo te llamas?"
            
            def hri_flow():
                self.set_robot_state("VISION")
                self.start_camera_tracking()
                
                # 1. Bienvenida y nombre
                self.speak_sync(pregunta)
                nombre = self.listen_sync("nombre") or "Desconocido"
                
                # 2. Preguntar edad
                self.speak_sync(f"Mucho gusto {nombre}. ¿Cuántos años tienes?")
                edad = self.listen_sync("edad") or "Desconocida"
                
                # 3. Despedida
                self.speak_sync(f"Gracias {nombre}, de {edad} años. Un placer.")
                
                # 4. Guardar datos
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                filename = "hri_interacciones.csv"
                file_exists = os.path.isfile(filename)
                
                with open(filename, 'a', newline='') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Fecha", "Nombre", "Edad", "Pregunta_Inicial"])
                    writer.writerow([timestamp, nombre, edad, pregunta])
                
                # 5. Detener
                self.stop_camera_tracking()
                self.set_robot_state("IDLE")
                self.after(0, finish_node)
                
            threading.Thread(target=hri_flow, daemon=True).start()

        elif node.node_type == "blink":
            try:
                times = int(node.repeat_entry.get())
                speed = node.speed_slider.get()
            except:
                times = 1
                speed = 0.3
                
            self.blink_eyes(times=times, speed=speed, finish_callback=finish_node)
            
        elif node.node_type == "jaw":
            try:
                times = int(node.repeat_entry.get())
                rtype = node.routine_type.get()
                spd = node.speed_slider.get()
            except:
                times = 1
                rtype = "Simple"
                spd = 0.4
            self.jaw_routine(times=times, routine_type=rtype, speed=spd, finish_callback=finish_node)
            
        elif node.node_type == "led":
            num_str = node.led_num.get()
            color_name = node.led_color.get()
            
            colors = {
                "Rojo": (255, 0, 0),
                "Verde": (0, 255, 0),
                "Azul": (0, 0, 255),
                "Cian": (0, 255, 255),
                "Apagar": (0, 0, 0)
            }
            r, g, b = colors.get(color_name, (0, 0, 0))
            
            if num_str == "LED 1":
                self.send_raw_command(f"L1 R{r} G{g} B{b}\n")
            elif num_str == "LED 2":
                self.send_raw_command(f"L2 R{r} G{g} B{b}\n")
            else: # Ambos
                self.send_raw_command(f"L1 R{r} G{g} B{b}\n")
                self.send_raw_command(f"L2 R{r} G{g} B{b}\n")
            
            self.after(50, finish_node)

        elif node.node_type == "stop":
            self.stop_sequence()


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
            if n.node_type == "jaw":
                widget_value = {"routine": n.routine_type.get(), "repeat": n.repeat_entry.get(), "speed": n.speed_slider.get()}
            elif n.node_type == "blink":
                widget_value = {"repeat": n.repeat_entry.get(), "speed": n.speed_slider.get()}
            elif n.node_type == "led":
                widget_value = {"led_num": n.led_num.get(), "led_color": n.led_color.get()}
            else:
                widget_value = n.widget.get() if n.widget else None
                
            nd = {
                "type": n.node_type,
                "x": n.x,
                "y": n.y,
                "widget_value": widget_value
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
            node_map = {}
            nodes_list = diagram.get("nodes", [])
            for i, nd in enumerate(nodes_list):
                n = self.add_node(nd["type"], nd["x"], nd["y"])
                node_map[i] = n
                val = nd.get("widget_value")
                if val is not None:
                    if n.node_type == "jaw" and isinstance(val, dict):
                        n.routine_type.set(val.get("routine", "Simple"))
                        n.repeat_entry.delete(0, "end")
                        n.repeat_entry.insert(0, str(val.get("repeat", "3")))
                        n.speed_slider.set(float(val.get("speed", 0.4)))
                    elif n.node_type == "blink" and isinstance(val, dict):
                        n.repeat_entry.delete(0, "end")
                        n.repeat_entry.insert(0, str(val.get("repeat", "3")))
                        n.speed_slider.set(float(val.get("speed", 0.3)))
                    elif n.node_type == "led" and isinstance(val, dict):
                        n.led_num.set(val.get("led_num", "LED 1"))
                        n.led_color.set(val.get("led_color", "Rojo"))
                    elif n.widget:
                        if hasattr(n.widget, 'delete') and hasattr(n.widget, 'insert'):
                            n.widget.delete(0, "end")
                            n.widget.insert(0, str(val))
                        elif hasattr(n.widget, 'set'):
                            n.widget.set(str(val))
                n.update_size()
            
            # Create edges
            for ed in diagram.get("edges", []):
                s_idx = ed["source"]
                t_idx = ed["target"]
                if s_idx in node_map and t_idx in node_map:
                    s_node = node_map[s_idx]
                    t_node = node_map[t_idx]
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
