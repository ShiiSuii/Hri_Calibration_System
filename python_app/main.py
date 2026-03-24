import customtkinter as ctk
import serial
import serial.tools.list_ports
import json
import os
import time

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"

class ServoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Bandera de seguridad vital para evitar que el render inicial de los sliders bombardee el Arduino
        self.gui_loaded = False 
        
        self.title("Calibrador y Framework de Robótica")
        self.geometry("1200x850")
        
        self.serial_port = None
        self.servos = []
        self.custom_actions = []
        
        self.sliders = {}
        self.labels = {}
        self.after_ids = {}
        self.entries = {}
        self.action_ui_entries = []
        
        self.running = True
        
        self.load_config()
        self.build_ui()
        
        self.gui_loaded = True
        
        # Conectar Serial después de que la interfaz gráfica ya arrancó
        self.after(200, self.delayed_startup)
        
    def delayed_startup(self):
        self.auto_connect_serial()
        # Empezar a leer del Arduino 1 segundo después (así le damos tiempo a revivir si se reinició)
        self.after(1000, self.check_serial)

    def check_serial(self):
        if self.running and self.serial_port and getattr(self.serial_port, 'is_open', False):
            try:
                while getattr(self.serial_port, 'in_waiting', 0) > 0:
                    try:
                        line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                        if line.startswith("I2C_SCAN:"):
                            result = line.replace("I2C_SCAN:", "").strip()
                            self.show_i2c_results(result)
                    except:
                        pass
            except Exception:
                pass
                
        if self.running:
            self.after(150, self.check_serial)

    def default_actions(self):
        return [
            # Acciones para Cuello (0x43, canales 16+)
            {"name": "Cuello: Posición Neutra", "config": "16:M, 17:M, 18:M"},
            {"name": "Cuello: Girar a Izquierda", "config": "16:600, 17:150"},
            {"name": "Cuello: Girar a Derecha", "config": "16:150, 17:600"},
            {"name": "Cuello: Dormido", "config": "16:328, 17:306, 18:500, 19:375"},
            {"name": "Cuello: Despierto", "config": "16:M, 17:M, 18:M, 19:M"},
            
            # Acciones para Cráneo (0x40, canales 0-15)
            {"name": "Cráneo: Posición Neutra", "config": "0:M, 1:M, 2:M"},
            {"name": "Cráneo: Abrir Mandíbula", "config": "0:364"},
            {"name": "Cráneo: Cerrar Mandíbula", "config": "0:257"},
            {"name": "Cráneo: Dormido", "config": "0:M, 1:M, 2:M"},
            {"name": "Cráneo: Despierto", "config": "0:M, 1:M, 2:M"}
        ]

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.servos = data
                        self.custom_actions = self.default_actions()
                    else:
                        self.servos = data.get("servos", [])
                        self.custom_actions = data.get("custom_actions", self.default_actions())
                        
                    self.servos = [s for s in self.servos if s["id"] < 20]
                    existing_ids = [s["id"] for s in self.servos]
                    for i in range(20):
                        if i not in existing_ids:
                            self.servos.append({"id": i, "name": f"Motor {i}", "min": 150, "max": 600, "mid": 375, "current": 375})
                    self.servos.sort(key=lambda x: x["id"])
                        
                    for s in self.servos:
                        if "name" not in s:
                            s["name"] = f"Motor {s['id']}"
            except Exception:
                self.create_default_config()
        else:
            self.create_default_config()

    def create_default_config(self):
        self.servos = []
        for i in range(20):
            self.servos.append({"id": i, "name": f"Motor {i}", "min": 150, "max": 600, "mid": 375, "current": 375})
        self.custom_actions = self.default_actions()
    
    def save_config(self):
        for i, config in enumerate(self.servos):
            ch_id = config["id"]
            try:
                config["name"] = self.entries[ch_id]["name"].get()
                config["min"] = int(self.entries[ch_id]["min"].get())
                config["mid"] = int(self.entries[ch_id]["mid"].get())
                config["max"] = int(self.entries[ch_id]["max"].get())
                self.sliders[ch_id].configure(from_=config["min"], to=config["max"])
            except ValueError:
                pass
                
        self.custom_actions = []
        for act_ui in self.action_ui_entries:
            name_val = act_ui["name_e"].get()
            cfg_val = act_ui["cfg_e"].get()
            self.custom_actions.append({"name": name_val, "config": cfg_val})
            
        data_to_save = {
            "servos": self.servos,
            "custom_actions": self.custom_actions
        }
                
        with open(CONFIG_FILE, "w") as f:
            json.dump(data_to_save, f, indent=4)
        print("Configuración guardada en config.json")

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
                
                # Vaciar la basura generada por el reinicio del Arduino
                if self.serial_port.is_open:
                    self.serial_port.reset_input_buffer()
                    self.serial_port.reset_output_buffer()
                    
                print(f"Conectado a {arduino_port}")
                self.status_label.configure(text=f"Conectado a {arduino_port}", text_color="#2ea043")
            except Exception as e:
                print(f"Error al conectar con {arduino_port}: {e}")
                self.status_label.configure(text=f"Error al conectar: {e}", text_color="#f85149")

    def send_command(self, channel, pulse):
        if not self.gui_loaded: return # Protección anti-SegFault durante __init__
            
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            cmd = f"C{channel} P{pulse}\n"
            try:
                self.serial_port.write(cmd.encode())
            except:
                pass

    def send_raw_command(self, cmd):
        if not self.gui_loaded: return
            
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            try:
                self.serial_port.write(cmd.encode())
            except:
                pass

    def on_slider_move(self, value, channel):
        pulse = int(value)
        self.labels[channel].configure(text=str(pulse))
        self.servos[channel]["current"] = pulse
        
        self.send_command(channel, pulse)
        
        # Control anti-rezagos
        if channel in self.after_ids:
            self.after_cancel(self.after_ids[channel])
        # Auto-cortar la corriente
        self.after_ids[channel] = self.after(500, lambda: self.send_command(channel, 0))

    def test_mid(self, channel):
        try:
            mid = int(self.entries[channel]["mid"].get())
            self.sliders[channel].set(mid)
            self.on_slider_move(mid, channel)
        except ValueError:
            pass

    def scan_i2c(self):
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            self.i2c_label.configure(text="Escaneando I2C...", text_color="#f2cc60")
            self.send_raw_command("S\n")

    def show_i2c_results(self, result):
        if result == "NONE":
            self.i2c_label.configure(text="I2C: Ningún dispositivo encontrado", text_color="#f85149")
        else:
            self.i2c_label.configure(text=f"I2C Encontrados: {result}", text_color="#2ea043")

    def execute_custom_action(self, cfg_str):
        moves = []
        try:
            parts = cfg_str.split(",")
            for p in parts:
                if ":" in p:
                    ch, pulse = p.split(":")
                    if pulse.strip().upper() == "M":
                        try:
                            pulse_val = int(self.entries[int(ch.strip())]["mid"].get())
                        except:
                            pulse_val = 375
                    else:
                        pulse_val = int(pulse.strip())
                    moves.append((int(ch.strip()), pulse_val))
        except Exception:
            return
            
        for ch, pulse in moves:
            try:
                self.sliders[ch].set(pulse)
                self.on_slider_move(pulse, ch)
            except:
                pass

    def build_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(pady=10, fill="x")
        
        title = ctk.CTkLabel(header_frame, text="Robot Framework & Sequencer", font=ctk.CTkFont(size=28, weight="bold"))
        title.pack()
        
        self.status_label = ctk.CTkLabel(header_frame, text="Esperando inicialización...", font=ctk.CTkFont(size=14), text_color="#f2cc60")
        self.status_label.pack()
        
        self.i2c_label = ctk.CTkLabel(header_frame, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.i2c_label.pack()
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=5)
        
        self.tab_calib = self.tabview.add("Calibración")
        self.tab_acciones = self.tabview.add("Acciones Dinámicas")
        
        # ---------------------------
        # TAB 1: CALIBRACION
        # ---------------------------
        header_calib = ctk.CTkFrame(self.tab_calib, fg_color="transparent")
        header_calib.pack(fill="x")
        ctk.CTkButton(header_calib, text="Escanear Puertos I2C", command=self.scan_i2c, width=150).pack(pady=5)
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.tab_calib)
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.scroll_frame.grid_columnconfigure((0,1,2,3), weight=1)
        
        lbl_cuello = ctk.CTkLabel(self.scroll_frame, text="Cuello Robótico (0x43)", font=ctk.CTkFont(size=18, weight="bold"), text_color="#58a6ff")
        lbl_cuello.grid(row=0, column=0, columnspan=4, pady=(10, 5))
        
        lbl_craneo = ctk.CTkLabel(self.scroll_frame, text="Cráneo Robótico (0x40)", font=ctk.CTkFont(size=18, weight="bold"), text_color="#58a6ff")
        lbl_craneo.grid(row=5, column=0, columnspan=4, pady=(20, 5))
        
        for config in self.servos:
            ch = config['id']
            # Mostrar 0x43 primero
            if ch >= 16:
                row = 1 + ((ch - 16) // 4)
                col = (ch - 16) % 4
            else:
                row = 6 + (ch // 4)
                col = ch % 4
            
            frame = ctk.CTkFrame(self.scroll_frame)
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            top_fs = ctk.CTkFrame(frame, fg_color="transparent")
            top_fs.pack(fill="x", pady=5)
            
            ch_lbl = ctk.CTkLabel(top_fs, text=f"CH{config['id']}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8b949e")
            ch_lbl.pack(side="left", padx=5)
            
            self.entries[config['id']] = {}
            
            name_entry = ctk.CTkEntry(top_fs, width=150, height=28, font=ctk.CTkFont(size=14, weight="bold"))
            name_entry.insert(0, config.get("name", f"Motor {config['id']}"))
            name_entry.pack(side="left", padx=5)
            self.entries[config['id']]["name"] = name_entry
            
            current_val = config.get("current", config["mid"])
            val_label = ctk.CTkLabel(frame, text=str(current_val), font=ctk.CTkFont(size=24, weight="bold"), text_color="#58a6ff")
            val_label.pack()
            self.labels[config['id']] = val_label
            
            # Aqui se creaba el SegFault, debido a que .set(current_val) disparaba la escritura por serial inmediatamente.
            # Ahora self.gui_loaded lo previene en send_command.
            slider = ctk.CTkSlider(frame, from_=config["min"], to=config["max"], command=lambda val, ch=config['id']: self.on_slider_move(val, ch))
            slider.set(current_val)
            slider.pack(pady=10, padx=10, fill="x")
            self.sliders[config['id']] = slider
            
            inputs_frame = ctk.CTkFrame(frame, fg_color="transparent")
            inputs_frame.pack(fill="x", padx=10)
            
            def create_entry(parent, label, key, ch_id):
                container = ctk.CTkFrame(parent, fg_color="transparent")
                container.pack(side="left", expand=True, padx=2)
                lbl = ctk.CTkLabel(container, text=label, font=ctk.CTkFont(size=12))
                lbl.pack()
                entry = ctk.CTkEntry(container, width=50, justify="center")
                entry.insert(0, str(self.servos[ch_id][key]))
                entry.pack()
                self.entries[ch_id][key] = entry
            
            create_entry(inputs_frame, "MIN", "min", config['id'])
            create_entry(inputs_frame, "MID", "mid", config['id'])
            create_entry(inputs_frame, "MAX", "max", config['id'])
            
            btn = ctk.CTkButton(frame, text="Probar MID", fg_color="#30363d", hover_color="#4b5563", command=lambda ch=config['id']: self.test_mid(ch))
            btn.pack(pady=10)
            
        footer_calib = ctk.CTkFrame(self.tab_calib, fg_color="transparent")
        footer_calib.pack(pady=10, fill="x")
        ctk.CTkButton(footer_calib, text="Guardar Configuración Base", font=ctk.CTkFont(size=16, weight="bold"), 
                                fg_color="#2ea043", hover_color="#238636", height=40, command=self.save_config).pack()

        # ---------------------------
        # TAB 2: ACCIONES
        # ---------------------------
        desc_frame = ctk.CTkFrame(self.tab_acciones, fg_color="#161b22")
        desc_frame.pack(pady=10, fill="x", padx=20, ipady=10)
        
        ctk.CTkLabel(desc_frame, text="Configurador Dinámico de Acciones", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=5)
        ctk.CTkLabel(desc_frame, text="Formato: Canal:Pulso separados por coma (ej: 0:500, 1:M).", font=ctk.CTkFont(size=14)).pack()
        
        self.actions_scroll = ctk.CTkScrollableFrame(self.tab_acciones, fg_color="transparent")
        self.actions_scroll.pack(pady=5, expand=True, fill="both")
        
        def delete_action_row(row_frame, entry_dict):
            row_frame.destroy()
            if entry_dict in self.action_ui_entries:
                self.action_ui_entries.remove(entry_dict)

        def append_action_row(act):
            row = ctk.CTkFrame(self.actions_scroll, fg_color="#21262d", corner_radius=6)
            row.pack(pady=5, fill="x", padx=10, ipady=5)
            
            name_e = ctk.CTkEntry(row, width=200, justify="center", font=ctk.CTkFont(size=14, weight="bold"))
            name_e.insert(0, act.get("name", ""))
            name_e.pack(side="left", padx=10)
            
            cfg_e = ctk.CTkEntry(row, width=400, font=ctk.CTkFont(size=14))
            cfg_e.insert(0, act.get("config", ""))
            cfg_e.pack(side="left", padx=10, fill="x", expand=True)
            
            entry_dict = {"name_e": name_e, "cfg_e": cfg_e}
            
            del_btn = ctk.CTkButton(row, text="🗑 Quitar", width=80, height=35, fg_color="#da3633", hover_color="#f85149", font=ctk.CTkFont(size=14, weight="bold"), command=lambda r=row, d=entry_dict: delete_action_row(r, d))
            del_btn.pack(side="right", padx=(5, 10))
            
            btn = ctk.CTkButton(row, text="▶ Ejecutar", width=120, height=35, font=ctk.CTkFont(size=14, weight="bold"), command=lambda e=cfg_e: self.execute_custom_action(e.get()))
            btn.pack(side="right", padx=5)
            
            self.action_ui_entries.append(entry_dict)

        for act in self.custom_actions:
            append_action_row(act)

        ctk.CTkButton(self.tab_acciones, text="+ Agregar Acción en blanco", fg_color="#30363d", hover_color="#4b5563", command=lambda: append_action_row({"name": "Nueva Acción", "config": ""})).pack(pady=5)
        
        footer_act = ctk.CTkFrame(self.tab_acciones, fg_color="transparent")
        footer_act.pack(pady=10, fill="x")
        ctk.CTkButton(footer_act, text="Guardar Nombres y Acciones", font=ctk.CTkFont(size=16, weight="bold"), 
                                fg_color="#2ea043", hover_color="#238636", height=40, command=self.save_config).pack()



    def on_closing(self):
        self.running = False
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            try:
                self.serial_port.close()
            except:
                pass
        self.destroy()

if __name__ == "__main__":
    app = ServoApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
