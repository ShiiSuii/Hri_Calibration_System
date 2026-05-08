import customtkinter as ctk
from PIL import Image
import os
from servo_app import ServoApp
from node_sequencer import NodeSequencerApp

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MainHub(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema Principal HRI")
        self.geometry("1200x900")
        
        # Cargar imagen generada
        self.image_path = "/home/ubuntu/.gemini/antigravity/brain/6275b49a-460d-4adf-aa15-be8d4d5b791c/robot_photo_1776269036912.png"
        self.robot_img = None
        if os.path.exists(self.image_path):
            img = Image.open(self.image_path)
            self.robot_img = ctk.CTkImage(light_image=img, dark_image=img, size=(320, 320))
        
        self.menu_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.menu_frame.pack(fill="both", expand=True)
        self.active_frame = None
        
        self.build_ui()
        
    def build_ui(self):
        header_frame = ctk.CTkFrame(self.menu_frame, fg_color="transparent")
        header_frame.pack(pady=40, fill="x")
        
        titulo = ctk.CTkLabel(header_frame, text="Bienvenido al Sistema HRI", font=ctk.CTkFont(size=36, weight="bold"))
        titulo.pack(pady=10)
        
        if self.robot_img:
            img_label = ctk.CTkLabel(header_frame, image=self.robot_img, text="")
            img_label.pack(pady=20)
        
        btn_frame = ctk.CTkFrame(self.menu_frame, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x")
        
        btn_font = ctk.CTkFont(size=20, weight="bold")
        
        btn_calibrar = ctk.CTkButton(btn_frame, text="Calibrar Motores", font=btn_font, height=60, width=350, fg_color="#1f6feb", hover_color="#388bfd",
                                     command=lambda: self.abrir_servo_app("Calibración"))
        btn_calibrar.pack(pady=15)
        
        btn_movimientos = ctk.CTkButton(btn_frame, text="Crear Movimientos Nuevos", font=btn_font, height=60, width=350, fg_color="#8957e5", hover_color="#a371f7",
                                        command=lambda: self.abrir_servo_app("Acciones Dinámicas"))
        btn_movimientos.pack(pady=15)
        
        btn_secuenciador = ctk.CTkButton(btn_frame, text="Node Sequencer", font=btn_font, height=60, width=350, fg_color="#2ea043", hover_color="#238636",
                                         command=self.abrir_node_sequencer)
        btn_secuenciador.pack(pady=15)
        
    def abrir_servo_app(self, tab):
        self.menu_frame.pack_forget()
        self.active_frame = ServoApp(self, return_callback=self.volver_al_menu, initial_tab=tab)
        self.active_frame.pack(fill="both", expand=True)
        
    def abrir_node_sequencer(self):
        self.menu_frame.pack_forget()
        self.active_frame = NodeSequencerApp(self, return_callback=self.volver_al_menu)
        self.active_frame.pack(fill="both", expand=True)

    def volver_al_menu(self):
        if self.active_frame:
            self.active_frame = None
        self.menu_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = MainHub()
    app.mainloop()
