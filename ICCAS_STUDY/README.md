# ICCAS Study — Pipeline de Interacción Humano-Robot

Sistema experimental de Interacción Humano-Robot (HRI) para el estudio ICCAS. El robot animatrónico percibe la atención del usuario mediante visión computacional, modula su comportamiento a través de una máquina de estados, y se comunica físicamente con un Arduino via puerto serial.

---

## Tabla de Contenidos

1. [Arquitectura General](#1-arquitectura-general)
2. [Módulos del Sistema](#2-módulos-del-sistema)
3. [Pipeline de Ejecución (Loop Principal)](#3-pipeline-de-ejecución-loop-principal)
4. [Comunicación con el Robot (Serial)](#4-comunicación-con-el-robot-serial)
5. [Máquina de Estados](#5-máquina-de-estados)
6. [Canales de Servomotores](#6-canales-de-servomotores)
7. [Motor de Percepción Visual (VisionPerception)](#7-motor-de-percepción-visual-visionperception)
8. [Worker de Visión por Lenguaje (VLMWorker)](#8-worker-de-visión-por-lenguaje-vlmworker)
9. [Motor de Voz (SpeechEngine)](#9-motor-de-voz-speechengine)
10. [Sistema de Logging](#10-sistema-de-logging)
11. [Instalación y Ejecución](#11-instalación-y-ejecución)

---

## 1. Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (Dashboard Tkinter)              │
│  Hilo Principal UI ─────────────────────────────────────────    │
│                                  │                              │
│              ┌───────────────────▼────────────────────┐        │
│              │      run_experiment_loop() [Thread]      │        │
│              │                                          │        │
│  ┌───────────┴──┐  ┌────────────┐  ┌──────────────┐   │        │
│  │ VisionPerc.  │  │ VLMWorker  │  │ StateMachine │   │        │
│  │ (MediaPipe)  │  │ (SmolVLM)  │  │              │   │        │
│  └──────┬───────┘  └─────┬──────┘  └──────┬───────┘   │        │
│         │  vision_results │  vlm_res        │ new_state  │        │
│         └────────────────┴────────────────►│           │        │
│                                             │           │        │
│                              ┌──────────────▼────────┐  │        │
│                              │   RobotController     │  │        │
│                              │  (Serial → Arduino)   │  │        │
│                              └───────────────────────┘  │        │
│                                                          │        │
│              ┌───────────────────────────────────────┐  │        │
│              │  SpeechEngine (gTTS + pygame)          │  │        │
│              └───────────────────────────────────────┘  │        │
│              ┌───────────────────────────────────────┐  │        │
│              │  StudyLogger (CSV + JSON)              │  │        │
│              └───────────────────────────────────────┘  │        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Módulos del Sistema

| Archivo | Clase | Responsabilidad |
|---|---|---|
| `main.py` | `ICCAS_Dashboard` | Dashboard Tkinter, loop principal, coordinación de módulos |
| `state_machine.py` | `StateMachine` | Lógica de estados del robot y transiciones |
| `robot_control.py` | `RobotController` | Control serial del Arduino, interpolación de servos, animaciones |
| `vision.py` | `VisionPerception` | Detección de rostro y estimación de atención (MediaPipe + PnP) |
| `vlm_worker.py` | `VLMWorker` | Clasificación semántica de la escena con SmolVLM (hilo separado) |
| `speech.py` | `SpeechEngine` | Generación y reproducción de audio (gTTS + pygame) |
| `logger.py` | `StudyLogger` | Registro de eventos por experimento en CSV y JSON |

---

## 3. Pipeline de Ejecución (Loop Principal)

El experimento corre en un **hilo separado** (`run_experiment_loop`) a ~50Hz. Cada iteración sigue estos 6 pasos en orden:

```
Cada frame (~20ms):
┌─────────────────────────────────────────────────────────────┐
│ 1. PERCEPCIÓN                                               │
│    cap.read() → MediaPipe FaceMesh → vision_results         │
│    (cada 2s) → VLMWorker.analyze_frame() → vlm_res          │
│                                                             │
│ 2. INPUT DEL EXPERIMENTADOR                                 │
│    Tecla 's' → sm.trigger_user_question()                   │
│    Tecla 'q' → stop_experiment()                            │
│                                                             │
│ 3. ACTUALIZACIÓN DE ESTADO                                  │
│    sm.update(vision_results, vlm_res, speech_status)        │
│    → new_state, event_note                                  │
│                                                             │
│ 4. CONTROL DE ROBOT Y AUDIO                                 │
│    Si new_state cambió → robot.apply_state(new_state)       │
│    Si tracking activo  → robot.track_face(cx, cy)           │
│    Si audio pendiente  → speech.play(audio_key)             │
│    robot.set_speaking(speech.is_busy())                     │
│                                                             │
│ 5. RENDER DE UI                                             │
│    frame → canvas Tkinter                                   │
│    state_lbl, vlm_lbl, audio_lbl actualizados               │
│                                                             │
│ 6. LOGGING                                                  │
│    logger.log_event(state, vlm_res, attention, event_note)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Comunicación con el Robot (Serial)

### Conexión

`RobotController` detecta automáticamente el Arduino buscando en todos los puertos COM/USB disponibles:

```python
# Se busca cualquier puerto que contenga "Arduino", "ACM" o "USB"
serial.Serial(p.device, baudrate=115200, timeout=0.1)
```

Si no hay Arduino conectado, el sistema entra en **modo simulado** (sin errores fatales).

### Protocolo de Comandos

La comunicación es unidireccional (PC → Arduino). Cada comando tiene el formato:

```
C<canal> P<pulso>\n
```

| Ejemplo | Significado |
|---|---|
| `C18 P362\n` | Mover servo del canal 18 a pulso 362 |
| `C0 P257\n` | Mover mandíbula (canal 0) a posición 257 |
| `C4 P0\n` | **Apagar** servo del canal 4 (desenergizar) |

### Hilos de Control en RobotController

El controlador ejecuta **dos hilos en paralelo** en background:

#### `_update_loop` (50Hz)
- **Interpolación suave**: avanza cada servo paso a paso (`slow_speed=2` o `normal_speed=10`) hacia su `target_position`.
- **Auto-OFF**: si un servo alcanzó su target y no se le pide cambio por **5 segundos**, envía `P0` para desenergizarlo (evita calentamiento).
- **Animación de mandíbula**: si `is_speaking=True`, genera una oscilación sinusoidal en el canal 0 (mandíbula) simulando habla.

#### `_blink_loop`
- Cada 3–7 segundos (aleatoriamente), realiza un **parpadeo**:
  1. Apaga los servos oculares de rotación (ch 4, 5, 7, 10) 1s antes.
  2. Cierra párpados (ch 11, 9, 8, 6) durante 150ms.
  3. Vuelve a la posición anterior.

---

## 5. Máquina de Estados

La `StateMachine` controla el flujo de la interacción. Se actualiza cada frame con `sm.update()`.

### Diagrama de Transiciones

```
                    ┌──────────┐
         ┌──────────┤ SLEEPING ├──────────┐
         │          └────┬─────┘          │
         │         face_detected          │
         │               │                │
         │          ┌────▼──────────┐     │
         │          │PERSON_DETECTED│     │
         │          └────┬──────────┘     │
         │        is_looking (0.8s)       │
         │               │                │
         │      ┌────────▼─────────┐      │
         │      │ATTENTION_DETECTED│      │
         │      └────────┬─────────┘      │
         │           tecla 's'            │
         │               │                │
         │      ┌────────▼─────────┐      │
         │      │   INTERACTING    │──────┤
         │      └────────┬─────────┘      │  distraction (2s) [Cond. B]
         │               │                │
         │  no_face (4.5s)│          ┌────▼────┐
         │               │          │ WAITING  │
         │      ┌────────▼─────────┐└────┬─────┘
         │      │    FINISHED      │     │ is_looking (0.8s)
         │      └────────┬─────────┘┌────▼──────────────┐
         │               │          │ RESUME_INTERACTION │
         └───────────────┘          └────────────────────┘
               despedida.finish            │ reanudacion.finish
                                           └──► INTERACTING
```

### Descripción de Cada Estado

| Estado | Descripción | Audio Disparado | Vel. Robot |
|---|---|---|---|
| **`sleeping`** | Robot dormido, ojos cerrados. Espera detectar un rostro. | — | Lenta |
| **`person_detected`** | Rostro detectado. Robot despierta y abre los ojos. Espera confirmación de atención. | `apertura` | Lenta |
| **`attention_detected`** | El usuario lleva ≥0.8s mirando al robot. Espera que el experimentador presione **`s`**. | `disponibilidad` | Normal |
| **`interacting`** | Robot ejecutando la explicación principal. En Condición B, detecta distracciones. | `respuesta` | Normal |
| **`waiting`** | Usuario distraído (≥2s sin mirar). Robot pausa el audio y espera. | `pausa` | Normal |
| **`resume_interaction`** | Usuario volvió a mirar (≥0.8s). Robot anuncia que continúa. | `reanudacion` | Normal |
| **`finished`** | Usuario se fue (≥4.5s sin rostro) o terminó la respuesta. Se despide. | `despedida` / `cierre` | — |

### Condiciones Experimentales

| Condición | Comportamiento |
|---|---|
| **A** | El robot no reacciona a distracciones. Reproduce la explicación completa sin interrupciones. |
| **B** | El robot detecta cuando el usuario deja de mirar (>2s) y pausa el audio. Reanuda cuando recupera la atención. |

### Teclas de Control

| Tecla | Acción |
|---|---|
| `s` | Dispara la pregunta del usuario → transición `attention_detected` → `interacting` |
| `q` | Detiene el experimento inmediatamente |

---

## 6. Canales de Servomotores

Los servos se controlan vía PCA9685 (I2C → Arduino). Cada canal tiene una función específica:

| Canal | Parte del Robot | Notas |
|---|---|---|
| **0** | Mandíbula | Oscila durante `is_speaking`. Cerrada = 257 |
| **4** | Ojo izq. — Rotación horizontal | Eye tracking horizontal |
| **5** | Ojo izq. — Rotación vertical | Eye tracking vertical |
| **6** | Párpado inferior izq. | Parpadeo |
| **7** | Ojo der. — Rotación vertical | Eye tracking vertical |
| **8** | Párpado superior der. | Parpadeo |
| **9** | Párpado inferior der. | Parpadeo |
| **10** | Ojo der. — Rotación horizontal | Eye tracking horizontal |
| **11** | Párpado superior izq. | Parpadeo |
| **18** | Cuello — Inclinación (Tilt) | Control de postura cabeza |
| **19** | Cuello — Giro (Pan) | Actualmente fijo en 375 |

### Posiciones por Estado

```python
state_dictionary = {
    "sleeping":            { 18:500, 19:375, ojos_cerrados, 0:257 },
    "person_detected":     { 18:362, 19:375, ojos_abiertos,  0:257 },
    "attention_detected":  { 18:350, 19:375, ojos_bien_abiertos, 0:257 },
    "interacting":         { 18:362, 19:375, ojos_abiertos,  0:257 },
    "waiting":             { 18:400, 19:375, párpados_mitad, 0:257 },
    "resume_interaction":  { 18:362, 19:375, ojos_abiertos,  0:257 },
}
```

### Eye Tracking (Zonas 3×3)

Cuando el tracking está activo, la pantalla se divide en una grilla 3×3. El centro (35%–65% del frame) es zona neutra:

```
┌──────────┬──────────┬──────────┐  Offsets de pan  (-50, 0, +50)
│  (L,A)   │  (C,A)   │  (R,A)   │  Offsets de tilt (-40, 0, +40)
├──────────┼──────────┼──────────┤
│  (L,C)   │ [NEUTRO] │  (R,C)   │
├──────────┼──────────┼──────────┤
│  (L,B)   │  (C,B)   │  (R,B)   │
└──────────┴──────────┴──────────┘
```

---

## 7. Motor de Percepción Visual (`VisionPerception`)

Usa **MediaPipe FaceMesh** con estimación de pose de cabeza (PnP solver):

1. **Detección**: MediaPipe extrae 478 landmarks faciales en tiempo real.
2. **Estimación de pose**: 6 puntos clave (nariz, mentón, ojos, boca) se resuelven con `cv2.solvePnP` para obtener **pitch**, **yaw** y **roll**.
3. **Heurística de atención**: El usuario "mira al robot" si `-30° < pitch < 30°` y `-30° < yaw < 30°`.
4. **Centro de rostro**: Landmark de nariz (idx=1) normalizado → `face_center (cx, cy)` para eye tracking.

```python
vision_results = {
    "face_detected": bool,
    "is_looking":    bool,
    "pitch":         float,   # grados verticales
    "yaw":           float,   # grados horizontales
    "roll":          float,
    "face_center":   (float, float),  # normalizados 0.0–1.0
    "frame":         np.ndarray
}
```

---

## 8. Worker de Visión por Lenguaje (`VLMWorker`)

Usa el modelo **SmolVLM-500M-Instruct** (HuggingFace) en un **hilo independiente** para no bloquear el loop principal.

- Se analiza **un frame cada 2 segundos** (para no saturar CPU/GPU).
- El prompt clasifica la escena en exactamente una de estas etiquetas:

| Etiqueta VLM | Interpretación en `state_machine.py` |
|---|---|
| `MIRANDO_AL_ROBOT` | Fuerza `is_looking = True` |
| `MIRANDO_CELULAR` | Fuerza `is_looking = False` |
| `MIRANDO_FUERA` | Fuerza `is_looking = False` |
| `SIN_PERSONA` | No modifica; la ausencia la detecta MediaPipe |

> Si `transformers` no está instalado, el worker entra en **modo simulación** y devuelve siempre `MIRANDO_AL_ROBOT`.

---

## 9. Motor de Voz (`SpeechEngine`)

Al iniciar el experimento, genera todos los audios con **gTTS** y los guarda como `.mp3` temporales. La reproducción usa **pygame.mixer**.

### Guion Completo

| Clave | Texto | Cuándo se reproduce |
|---|---|---|
| `apertura` | *"Hola. Estoy listo para conversar."* | Al despertar (`person_detected`) |
| `disponibilidad` | *"Te escucho."* | Al confirmar atención |
| `respuesta` | Explicación de IA (~3 párrafos) | Al presionar **`s`** |
| `pausa` | *"Te espero."* | Al detectar distracción (Cond. B) |
| `reanudacion` | *"Continúo."* | Al recuperar atención |
| `cierre` | *"Eso es, de forma breve, la inteligencia artificial."* | Al finalizar `respuesta` |
| `despedida` | *"Hasta luego."* | Al detectar ausencia prolongada |

### Lógica de Espera para Audio

Algunos audios se retrasan deliberadamente para sincronizar con el movimiento del robot:

- **`apertura`**: se espera que el robot termine de interpolar (no `is_interpolating()`) **y** que hayan pasado ≥5s del wake-up.
- **`despedida`**: se espera que el robot termine de interpolar antes de reproducir.
- **`pausa` / `reanudacion`**: se crea un `SpeechEngine` temporal para no interferir con la pista principal.

---

## 10. Sistema de Logging

Cada experimento genera **dos archivos** en la carpeta `logs/`:

### CSV — Registro Frame a Frame

Nombre: `subj<ID>_cond<COND>_scen<SCEN>_<TIMESTAMP>.csv`

| Columna | Tipo | Descripción |
|---|---|---|
| `timestamp` | `HH:MM:SS.mmm` | Hora del evento |
| `elapsed_ms` | `int` | Milisegundos desde inicio del experimento |
| `state` | `str` | Estado actual de la máquina |
| `vlm_res` | `str` | Última clasificación del VLM |
| `attention` | `bool` | `True` si MediaPipe detectó que mira al robot |
| `event` | `str` | Nota de evento especial (e.g. `"Distraction detected"`) |

### JSON — Resumen del Experimento

Nombre: `subj<ID>_cond<COND>_scen<SCEN>_<TIMESTAMP>_summary.json`

```json
{
  "participant_id": "01",
  "condition": "B",
  "scenario": "2",
  "trial_start_time": "...",
  "person_detected_time": "HH:MM:SS",
  "attention_detected_time": "HH:MM:SS",
  "speech_start_time": "HH:MM:SS",
  "distraction_detected_time": "HH:MM:SS",
  "pause_triggered_time": "HH:MM:SS",
  "attention_recovered_time": null,
  "resume_triggered_time": "HH:MM:SS",
  "trial_end_time": "...",
  "state_sequence": ["sleeping", "person_detected", "attention_detected", "interacting", "waiting", ...],
  "motor_commands_count": 0
}
```

---

## 11. Instalación y Ejecución

### Requisitos

```bash
pip install -r requirements.txt
```

```
opencv-python==4.9.0.80
mediapipe==0.10.11
numpy<2.0.0
pygame==2.5.2
gTTS==2.5.1
pyserial==3.5
```

> Para el módulo VLM (opcional): `pip install transformers torch Pillow`

### Ejecución

```bash
cd ICCAS_STUDY
python main.py
```

### Parámetros del Dashboard

| Campo | Descripción | Valores |
|---|---|---|
| **Subject ID** | Identificador del participante | Texto libre (ej. `"01"`) |
| **Condition** | Condición experimental | `A` (sin reacción) / `B` (con pausa adaptativa) |
| **Scenario** | Escenario del experimento | `1` / `2` |
| **Camera Index** | Índice de la cámara USB | `0`, `1`, `2`, `3` |
| **Enable Eye Tracking** | Activa/desactiva el seguimiento ocular | Checkbox |

### Hardware Requerido

- Arduino (cualquier modelo con USB) con firmware de control PCA9685
- 1× o 2× módulos PCA9685 (I2C: `0x40` cráneo, `0x43` cuello)
- Servomotores conectados según la tabla de canales
- Cámara USB compatible con OpenCV

---

*Proyecto de Tesis — ICCAS 2025 | HRI Laboratory*
