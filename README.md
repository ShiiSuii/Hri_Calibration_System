# Framework HRI para Control Robótico Animatrónico (Proyecto de Tesis)

## 📖 Resumen del Proyecto
Este repositorio contiene un framework modular integral para la calibración, control y secuenciación de servomotores enfocado en la **Interacción Humano-Robot (HRI)**. Diseñado para dar vida a robots animatrónicos (como cráneos y cuellos biomecánicos), el sistema garantiza la seguridad térmica del hardware y proporciona un potente entorno de programación visual para crear animaciones complejas, flujos conversacionales y recolección de métricas de forma intuitiva.

## 🏗️ Arquitectura del Hardware
- **Microcontrolador**: Arduino (ej: Uno, Nano, Mega).
- **Controladores PWM**: 2x Módulos PCA9685 conectados vía bus I2C (Direcciones `0x40` para Cráneo y `0x43` para Cuello), lo cual permite escalar la estructura hasta 32 grados de libertad.
- **Indicadores de Estado Visual (LEDs RGB)**:
  - **LED 1 (Interacción / HRI)**: Integrado para debug visual de los estados del robot en tiempo real frente al usuario (Standby [Azul], Hablando [Verde], Escuchando [Cian], Grabando [Rojo]).
  - **LED 2 (Hardware / Energía)**: Actúa de forma completamente autónoma a nivel de firmware. Indica Verde en el instante que los motores están recibiendo torque y cambia a Azul cuando el sistema entra en reposo absoluto.
- **Seguridad (Safety Timeout Automatizado)**: El firmware escrito en C/C++ inyectado en el Arduino corta automáticamente la señal PWM (escribe pulso 0) de cualquier canal de motor que haya mantenido su posición fija durante un tiempo prolongado sin recibir nuevos comandos. Esto resuelve el clásico problema en la robótica de sobrecalentamiento y quema de los servomotores por estrés estático contra fuerza mecánica.

### Mapeo de Canales PCA9685
El sistema distribuye la asignaci\u00f3n anat\u00f3mica del robot a trav\u00e9s de los diversos canales PWM. Actualmente la configuraci\u00f3n se mapea de la siguiente manera:

**M\u00f3dulo 1 (`0x40`) - Cr\u00e1neo / Rostro (Canales 0 al 15):**
- **0**: Mand\u00edbula
- **1**: Labio Superior
- **2 y 3**: Cachetes (Derecho e Izquierdo)
- **4 y 5**: Ojo Derecho (Eje X/Y)
- **7 y 10**: Ojo Izquierdo (Eje Y/X)
- **6, 8, 9, 11**: P\u00e1rpados (Superiores e Inferiores, Izquierdo y Derecho)
- **12 al 15**: Cejas y Ce\u00f1o (Cejas D/I y Ce\u00f1os D/I)

**M\u00f3dulo 2 (`0x43`) - Cuello / Mec\u00e1nica Base (Canales 16 al 19):**
- **16 y 17**: Ejes de rotaci\u00f3n (Girar Izquierda/Derecha)
- **18**: Cuello/Frente (Movimiento Arriba/Abajo / Cabeceo)
- **19**: Cuello Lateral (Inclinaci\u00f3n hacia los hombros)

## \U0001f4bb Arquitectura del Software (Python)
Todo el software de control está desarrollado en Python utilizando la librería `customtkinter` para asegurar interfaces oscuras (`Dark Mode`), ágiles y modernas. La comunicación entre la PC y el Arduino se entabla universalmente mediante protocolo de puerto `Serial`. Todo el proyecto orbita en torno al archivo maestro `config.json`, el cual almacena la configuración de puertos y calibraciones.

### 1. Sistema de Calibración (`main.py`)
Módulo encargado del mapeo y setup físico del robot.
- **Calibración Segura (Limiting)**: El operador puede arrastrar _sliders_ visuales para configurar un límite de pulso Mínimo (`MIN`), Medio (`MID`) y Máximo (`MAX`) para cada respectivo servomotor conectado. Estos límites actúan como topes que protegen físicamente a la estructura de forzar o de enviar pulsos imposibles.
- **Prueba en Tiempo Real**: Al reubicar un slider de la interfaz, el software manda la instrucción en 0 latencia al Hardware. Cuando el operador suelta el cursor de su ratón automáticamente se emite la orden de detención energética segura (pulso 0) evitando el calentamiento mencionado.
- **Editor de Acciones Dinámicas**: Permite capturar las coordenadas actuales de todos los sliders alterados para guardarlas bajo un solo comando unificado o pose (por ejemplo: "Sonrisa Asimétrica", "Pestañeo Derecho").

### 2. Secuenciador Visual por Nodos (`node_sequencer.py`)
Módulo *Drag & Drop* basado visualmente en grafos, programado desde cero para diseñar flujos de tiempo. Se encarga de traducir las posturas estáticas creadas en `main.py` en verdaderas interacciones teatrales, de diálogo y recolección paramétrica.

**Características del Motor de Ejecución Visual:**
- **Ejecución Asíncrona Paralela**: El lienzo de trabajo permite enlazar múltiples "cables" en cadena directamente de un solo puerto de salida originario (creando un diagrama en forma de "Y" o más). Cuando el programa alcanza ese punto, todos los hilos correspondientes se distribuyen en forma concurrente. Esto abre la posibilidad, por ejemplo, que el robot en un momento empiece a relatar una historia mientras en simultáneo gesticula sus ojos y mueve el cuello.
- **Espacio de Trabajo Visual (Workspace)**: Los Nodos cuentan con redimensionamiento dinámico (ajustando su tamaño al texto) y una interfaz refinada con bordes redondeados. El fondo de cuadrícula (grid) y los colores son personalizables, permitiendo un entorno visual cómodo y profesional.
- **Almacenamiento Persistente**: Los diagramas de interacción (flujo y configuraciones) se almacenan localmente en repositorios JSON, posibilitando cargar trabajos previos y desarrollar coreografías por etapas.
- **Multicontrolador (Hardware Agnostic Pipeline)**: El backend expandido permite orquestar rutinas combinando múltiples placas PCA9685 a la vez (ej. Módulo `0x40` para maxilofacial y `0x43` para el cuello pélvico), logrando gestionar un enjambre de servomotores dirigiendo los paquetes a las direcciones específicas mediante el protocolo I2C.
- **Flujo Lógico**: El cableado libre define el orden de cascada.

**Catálogo de Nodos (Bloques HRI disponibles):**
1. 🟢 **Start**: Nodo inamovible que dicta el punto de entrada de la animación.
2. 🔵 **Acción**: Lee los paquetes guardados en `config.json` para ejecutar instantáneamente una pose del `main.py` y libera el flujo al próximo nodo en apenas \~100 milisegundos.
3. 🟡 **Delay**: Congela la bifurcación específica en su cuenta regresiva designada de milisegundos útiles en pausas comédicas o transiciones fluidas.
4. 🟣 **Hablar (TTS - Text to Speech)**: Un input de texto donde el organizador define qué debe pronunciar el robot. El sistema utiliza librería offline `pyttsx3` que transmite audio directo a la vez que cambia el `LED 1` a Verde. **Retiene el cable saliente (Flujo)** hasta que la I.A. termina de verbalizar las palabras exactas, otorgando así sincronía entre sonido y gestos siguientes temporizados.
5. 🩵 **Escuchar (STT - Speech to Text)**: Activa temporalmente el micrófono a la espera de un *Input* verbal del Humano con la que coincidir y enciende el LED 1 de forma Cian. Funciona como compuerta que no permitirá que la ejecución de la animación siga adelante a menos que la persona pronuncie la frase exacta designada en el nodo. Ideal para *Árboles de Diálogo Guiados*.
6. 🔴 **Cámara HRI / Metric Logging (NUEVO)**: Nodo de infraestructura investigativa implementado para permitir a este entorno recopilar Big Data real orientada a la Interacción Social de Humanos y Robots. Al ejecutarse una orden de *Iniciar Tracking*, interrumpe la animación y exhibe de imprevisto una ventana Pop-up forzando al operador al ingreso de datos demográficos del participante a sentarse (`Nombre, Edad, Carrera`). Posteriormente reanuda toda la animación e invoca una hebra secundaria en la que `OpenCV` toma control de la WebCam USB para el Head-Tracking y paralelamente genera localmente y de forma rítmica (aprox. 10 FPS) mediciones documentadas en un `.csv`, ideal como registrador de datos (Data Logger) activable a demanda desde el switch en la UI de la cámara.
7. 🛑 **Stop (NUEVO)**: Finaliza abruptamente la ejecución de cualquier rama del árbol o de la secuencia entera activa. Fundamental como medida de seguridad ante desincronizaciones de Hardware y como finalizador para diagramas asíncronos paralelos.

---

## 🚀 Capacidades y Potencial para Investigación HRI (Framework Escalable)

Este framework está concebido y estructurado no solo como una botonera de control robótico manual, sino como una **plataforma base de investigación paramétrica y escalable**, convirtiéndolo en un candidato ideal y robusto para Tesis de Sistemas e Investigaciones en el campo de *Human-Robot Interaction*. Sus horizontes de expansión futuros y presentes incluyen:

- **Integración Nativa de Machine/Deep Learning Visual**: Gracias a la arquitectura multihilo de Python, el sub-proceso actual de OpenCV (Cámara HRI) está específicamente diseñado para ser inyectable en código abierto. Un investigador puede adjuntar librerías de vanguardia como *DeepFace*, *MediaPipe* o *YOLO* para recolectar e inferir el género, la edad gestual, medir la microexpresión estresora (Emociones) o calcular la pose y línea de visión (Gaze Tracking) del humano con quien interactúa la máquina. Todo ello procesándose asíncronamente mientras el robot recita su guion por la rama motora principal.
- **Generación de Respuestas y Agente Conversacional vía LLM**: El sistema de Nodos Visuales actual ya domina el ciclo "Escuchar (Micrófono) -> Hablar (Altavoz)". Un paso lógico a integrar por la comunidad es un *Nodo Puente LLM* (ej. *Local Llama 3* o *OpenAI API*) que reciba el dictado capturado en STT, genere un razonamiento semántico contextual, y produzca respuestas de forma dinámica sin depender de un flujo lineal estricto en el diagrama nodal.
- **Biometrías Relacionadas a la Experiencia de Usuario (Logs Tabulares)**: El actual **Data Logger (.csv)** exporta una línea temporal sincronizada con lo que el robot dictaminó y con las coordenadas de seguimiento grabadas. Esto brinda a los facultativos cognitivos y psicólogos herramientas listas para realizar pruebas ciegas A/B directas sobre seres humanos ("¿Un robot con gestos amables incrementa o disminuye la retención o estrés de los alumnos?").
- **Teleoperación de Sistemas (WebSockets y API REST)**: Si bien por ahora la interacción entre el PC y el MCU es transaccional local por cable Serie USB de alta velocidad; construir un contenedor Flask o FastAPI alrededor de los diccionarios de posturas JSON permitiría la conectividad remota al Robot mediante Wi-Fi o red celular abriendo la puerta a exposiciones globales interactivas, teatro y teleoperación inmersiva.
- **Máxima Tolerancia Robótica Empírica**: Aprovechando al máximo el bus I2C para PCA9685, esta base en código y firmware puede ser llevada rápidamente para animar simultáneamente androides bipedales completos, exoesquéletos y parques temáticos asombrosos sumando hasta casi 1000 servomotores al mismo bus de 2 hilos sin requerir reeescribir la arquitectura troncal.
- **Independencia de Motores Modulares**: La evolución a un sistema acoplable ("cables" de nodos referenciando las acciones) divorcia el tiempo de la física; los temporizadores lógicos garantizan comportamientos expresivos a la par de la narración o música, loables de la industria audiovisual moderna.

---

## 🛠️ Requisitos e Instalación

### Hardware
- Arduino.
- 2x Módulos Servomotor PCA9685.
- Servomotores + Fuente de alimentación externa amperada correspondiente.
- 2 módulos LED RGB.
- Cámara Web y Micrófono (Requeridos para el uso óptimo de funciones STT y Log HRI).

### Software (Linux Core Dependencies)
Instale en su terminal de Linux (Ubuntu/Debian) el soporte fundamental antes del pipeline Python para garantizar compilación satisfactoria de las llaves de audio (`PyAudio`):
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio
```

### Inicialización Entorno Python
```bash
# Recomendado dentro de entorno virtual .venv
pip install -r python_app/requirements.txt
```

## 🚀 Cómo Iniciar el Framework
1. Conecta el USB del Arduino y energiza tu pared externa de Hardware.
2. Lanza el Calibrador Inicial primeramente para trazar el límite mecánico salvaguarda:
   ```bash
   python3 python_app/main.py
   ```
3. Ensambla y graba tus "Acciones" Dinámicas elementales (Sonrisas, Posiciones X/Y).
4. Cierra el calibrador. Enciende el Secuenciador para arrastrar los nodos a tu gráfica experimental:
   ```bash
   python3 python_app/node_sequencer.py
   ```
