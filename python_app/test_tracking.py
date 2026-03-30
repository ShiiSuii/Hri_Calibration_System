import cv2
import serial
import serial.tools.list_ports
import time
import os
import sys
import argparse

# Intentar encontrar la ruta de los Haar Cascades (especialmente si cv2.data no existe)
cascade_paths = [
    getattr(cv2, 'data', None).haarcascades if hasattr(cv2, 'data') and cv2.data else None,
    "/usr/share/opencv4/haarcascades/",
    "/usr/local/share/opencv4/haarcascades/",
    "/var/lib/opencv/haarcascades/"
]

face_cascade = None
for path in cascade_paths:
    if path:
        full_path = os.path.join(path, 'haarcascade_frontalface_default.xml')
        if os.path.exists(full_path):
            face_cascade = cv2.CascadeClassifier(full_path)
            print(f"Cargando cascada desde: {full_path}")
            break

if face_cascade is None or face_cascade.empty():
    # Intento final: buscar en el sistema si no se encontró en las rutas comunes
    print("Buscando haarcascade_frontalface_default.xml en el sistema...")
    # Esto es más lento pero asegura que funcione
    face_cascade = cv2.CascadeClassifier('/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml')

# Posiciones globales de los servos (empezando en el punto medio)
# Canal 18: Vertical (Arriba/Abajo)
pos18 = 362
# Canal 19: Lateral (Izquierda/Derecha)
pos19 = 375

def auto_connect_serial():
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
            return serial.Serial(arduino_port, 115200, timeout=1)
        except: pass
    return None

def send_command(ser, channel, pulse):
    if ser and ser.is_open:
        cmd = f"C{channel} P{pulse}\n"
        ser.write(cmd.encode())

import sys
import argparse

# ... (rest of imports)

def main():
    global pos18, pos19
    
    parser = argparse.ArgumentParser(description='Face Tracking Test with OpenCV')
    parser.add_argument('--cam', type=int, default=0, help='Index de la cámara (ej. 0 para interna, 1 o 2 para USB)')
    args = parser.parse_args()

    ser = auto_connect_serial()
    if not ser:
        print("Error: No se encontró Arduino.")
        return

    print(f"Abriendo cámara {args.cam}...")
    cap = cv2.VideoCapture(args.cam)
    if not cap.isOpened():
        print("Error: No se puede abrir la cámara.")
        return

    print("Iniciando Tracking Facial con OpenCV...")
    print("---------------------------------------")
    print("Canal 18: Vertical (Gira Arriba/Abajo)")
    print("Canal 19: Lateral (Gira Izquierda/Derecha)")
    print("Presiona 'q' para salir.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            # Voltear la imagen horizontalmente (efecto espejo)
            frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))

            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2

            # Dibujar mira central de referencia
            cv2.line(frame, (cx-20, cy), (cx+20, cy), (0, 255, 0), 1)
            cv2.line(frame, (cx, cy-20), (cx, cy+20), (0, 255, 0), 1)

            if len(faces) > 0:
                # Rastreamos la primera cara detectada
                (x, y, fw, fh) = faces[0]
                fx, fy = x + fw // 2, y + fh // 2
                
                cv2.rectangle(frame, (x, y), (x+fw, y+fh), (255, 0, 0), 2)
                cv2.circle(frame, (fx, fy), 5, (255, 0, 0), -1)

                # Lógica de Tracking (Aproximación Proporcional para Suavidad)
                error_x = fx - cx
                error_y = fy - cy
                
                # --- PARÁMETROS DE PRECISIÓN Y SUAVIDAD ---
                threshold = 15     # Deadzone menor = más preciso
                k_smooth = 25      # Divisor de suavidad (Más alto = más lento/suave)
                max_step = 10      # Límite de velocidad máxima por frame
                
                # Lateral (Canal 19)
                if abs(error_x) > threshold:
                    # Cálculo proporcional: a mayor distancia, paso más grande
                    var_step_x = min(max_step, max(1, int(abs(error_x) / k_smooth)))
                    if error_x > 0: pos19 -= var_step_x 
                    else:           pos19 += var_step_x
                
                # Vertical (Canal 18)
                if abs(error_y) > threshold:
                    var_step_y = min(max_step, max(1, int(abs(error_y) / k_smooth)))
                    if error_y > 0: pos18 += var_step_y
                    else:           pos18 -= var_step_y

                # Límites de seguridad (Safety constraints)
                pos18 = max(200, min(550, pos18))
                pos19 = max(150, min(600, pos19))

                # Enviar comandos al Arduino
                send_command(ser, 18, pos18)
                send_command(ser, 19, pos19)
                
                # Feedback visual de la corrección
                cv2.putText(frame, f"Corrección: 18:{pos18} 19:{pos19}", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

            cv2.imshow('OpenCV Tracking Test', frame)
            
            # Salir con 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nPrueba finalizada por el usuario.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if ser: 
            # Volver a posición neutra antes de cerrar
            send_command(ser, 18, 362)
            send_command(ser, 19, 375)
            time.sleep(0.5)
            ser.close()

if __name__ == "__main__":
    main()
