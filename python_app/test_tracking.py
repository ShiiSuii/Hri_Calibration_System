import cv2
import serial
import serial.tools.list_ports
import time
import os
import sys
import argparse
import mediapipe as mp
import random

# Inicializar MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

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



def main():
    global pos18, pos19
    
    parser = argparse.ArgumentParser(description='Face Tracking Test with OpenCV')
    parser.add_argument('--cam', type=int, default=2, help='Index de la cámara (ej. 0 para interna, 1 o 2 para USB)')
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

    print("Iniciando Tracking Facial con MediaPipe...")
    print("---------------------------------------")
    print("Canal 18: Vertical (Gira Arriba/Abajo)")
    print("Canal 19: Lateral (Gira Izquierda/Derecha)")
    print("Presiona 'q' para salir.")

    # Abrir ojos inicialmente
    send_command(ser, 11, 325)
    send_command(ser, 9, 270)
    send_command(ser, 8, 307)
    send_command(ser, 6, 430)
    
    last_blink_time = time.time()
    next_blink_delay = random.uniform(3.0, 7.0)
    last_move_time = 0.0

    try:
        while True:
            # Lógica de parpadeo natural
            # Sólo esperar un breve instante tras el último movimiento para no bloquear demasiado
            current_time = time.time()
            if (current_time - last_blink_time > next_blink_delay) and (current_time - last_move_time > 0.2):
                # --- PISCAR: pausar motores del cuello para no dividir corriente ---
                # Apagar servos de cuello para que no compitan con los ojos
                send_command(ser, 18, 0)
                send_command(ser, 19, 0)
                time.sleep(0.02) # breve pausa para que el comando llegue

                # Cerrar ojos lentamente (interpolación en pasos)
                OPEN  = {11: 325, 9: 270, 8: 307, 6: 430}
                CLOSE = {11: 285, 9: 306, 8: 249, 6: 464}
                STEPS = 8
                for step in range(1, STEPS + 1):
                    t = step / STEPS
                    for ch in OPEN:
                        pulse = int(OPEN[ch] + (CLOSE[ch] - OPEN[ch]) * t)
                        send_command(ser, ch, pulse)
                    time.sleep(0.022) # ~8 pasos * 22ms ≈ 175ms de cierre
                
                # Pausa con ojo cerrado
                time.sleep(0.05)
                
                # Abrir ojos lentamente
                for step in range(1, STEPS + 1):
                    t = step / STEPS
                    for ch in OPEN:
                        pulse = int(CLOSE[ch] + (OPEN[ch] - CLOSE[ch]) * t)
                        send_command(ser, ch, pulse)
                    time.sleep(0.022) # ~8 pasos * 22ms ≈ 175ms de apertura
                
                # Reactivar cuello en la posición actual (sin enviar 0 = off)
                send_command(ser, 18, pos18)
                send_command(ser, 19, pos19)

                last_blink_time = time.time()
                next_blink_delay = random.uniform(3.0, 7.0)

            ret, frame = cap.read()
            if not ret: break
            
            # Voltear la imagen horizontalmente (efecto espejo)
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)

            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2

            # Dibujar mira central de referencia
            cv2.line(frame, (cx-20, cy), (cx+20, cy), (0, 255, 0), 1)
            cv2.line(frame, (cx, cy-20), (cx, cy+20), (0, 255, 0), 1)

            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0]
                
                # Rastrear la punta de la nariz (landmark 1)
                nose_landmark = face_landmarks.landmark[1]
                fx = int(nose_landmark.x * w)
                fy = int(nose_landmark.y * h)
                
                # Dibujar malla facial y punto objetivo
                mp.solutions.drawing_utils.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=mp_face_mesh.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp.solutions.drawing_styles.get_default_face_mesh_contours_style()
                )
                cv2.circle(frame, (fx, fy), 8, (255, 0, 0), -1)

                # Lógica de Tracking (Aproximación Proporcional para Suavidad)
                error_x = fx - cx
                error_y = fy - cy
                
                # --- PARÁMETROS DE PRECISIÓN Y SUAVIDAD ---
                threshold = 15     # Deadzone menor = más preciso
                k_smooth = 40      # Divisor de suavidad aumentado (movimientos más naturales y lentos)
                max_step = 5       # Límite de velocidad máxima reducido para evitar movimientos bruscos
                
                # Bandera para saber si se está moviendo en este frame
                is_moving = False

                # Lateral (Canal 19)
                if abs(error_x) > threshold:
                    is_moving = True
                    # Cálculo proporcional: a mayor distancia, paso más grande
                    var_step_x = min(max_step, max(1, int(abs(error_x) / k_smooth)))
                    if error_x > 0: pos19 -= var_step_x 
                    else:           pos19 += var_step_x
                
                # Vertical (Canal 18)
                if abs(error_y) > threshold:
                    is_moving = True
                    var_step_y = min(max_step, max(1, int(abs(error_y) / k_smooth)))
                    if error_y > 0: pos18 += var_step_y
                    else:           pos18 -= var_step_y

                if is_moving:
                    last_move_time = time.time()

                # Límites de seguridad (Safety constraints)
                pos18 = max(200, min(550, pos18))
                pos19 = max(150, min(600, pos19))

                # Enviar comandos al Arduino
                send_command(ser, 18, pos18)
                send_command(ser, 19, pos19)
                
                # Feedback visual de la corrección
                cv2.putText(frame, f"Corrección: 18:{pos18} 19:{pos19}", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

            cv2.imshow('MediaPipe Tracking Test', frame)
            
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
