# Framework de Calibración y Control Robótico (Proyecto de Tesis)

Este repositorio contiene un framework modular diseñado para el control, calibración y secuenciación de múltiples servomotores utilizando microcontroladores Arduino y controladores PWM PCA9685. El propósito de este proyecto es facilitar la creación de animaciones y movimientos complejos (por ejemplo, en robótica animatrónica como un cráneo y un cuello) de forma segura y visual.

## 🏗️ Arquitectura del Proyecto

El proyecto está dividido en dos partes principales: el firmware que se ejecuta en el hardware (Arduino) y el software de control (Aplicaciones en Python con interfaz gráfica).

### 1. Firmware (Arduino)
Ubicación: `arduino/servo_controller/servo_controller.ino`

El firmware de Arduino actúa como el cerebro de bajo nivel del sistema. Recibe instrucciones a través del puerto Serie (USB) y las traduce en señales I2C para controlar las placas expansoras de PWM (PCA9685). 

**Características principales:**
- **Soporte Multi-Placa:** Configurado para manejar dos placas PCA9685 simultáneamente en las direcciones `0x40` (ej: Cráneo, canales 0-15) y `0x43` (ej: Cuello, canales 16-31).
- **Escáner I2C Integrado:** Permite a la aplicación de Python consultar y verificar qué dispositivos I2C están conectados y respondiendo enviando el comando `S\n`.
- **Protocolo de Comunicación Simple:** Recibe comandos en el formato `C<canal> P<pulso>\n` (ej. `C16 P300`).
- **Sistema de Auto-Apagado (Safety Timeout):** Monitorea el tiempo de activación de cada motor. Si un motor se mantiene energizado por más de 1000ms sin recibir un nuevo comando de posición, el Arduino automáticamente corta la señal PWM (escribe 4096). Esto es crucial para **evitar el sobrecalentamiento y la quema de los servomotores** cuando no se están moviendo, un problema común en robótica cuando los motores intentan mantener una posición contra fuerza mecánica.

### 2. Software de Control (Python)
Las herramientas de Python están construidas con la librería gráfica `customtkinter`, lo cual brinda una interfaz moderna y oscura. Ambas aplicaciones comparten el archivo `config.json` para mantener la sincronización de la calibración y las acciones creadas.

#### A. Calibrador y Creador de Acciones
Ubicación: `python_app/main.py`

Esta es la herramienta principal para inicializar la puesta a punto del robot.
- **Calibración de Límites:** Permite definir de forma gráfica los valores de pulso Mínimo (`MIN`), Medio (`MID`) y Máximo (`MAX`) para cada servo. Esto garantiza que las futuras secuencias nunca fuercen mecánicamente un motor más allá de sus límites físicos.
- **Prueba en Tiempo Real:** Al mover los sliders en la interfaz, el robot reacciona en tiempo real. Utiliza un sistema anti-rezagos que envía un pulso 0 al soltar el slider para confirmar el apagado seguro.
- **Creación de Acciones Dinámicas:** Permite agrupar las posiciones de múltiples motores bajo un nombre descriptivo (ej. "Cuello: Girar a Izquierda", "Cráneo: Abrir Mandíbula"). Estas acciones se guardan en el archivo de configuración.

#### B. Secuenciador Basado en Nodos
Ubicación: `python_app/node_sequencer.py`

Una herramienta visual e interactiva tipo "Drag and Drop" para programar comportamientos en el tiempo, desacoplada de la interfaz de calibración.
- **Nodos de Control:** Permite colocar en un lienzo virtual tres tipos de nodos: `Start` (Inicio), `Acción` (carga las acciones creadas en `main.py`) y `Delay` (Pausas en segundos).
- **Conexiones (Cableado):** El usuario puede "cablear" la salida de un nodo con la entrada del siguiente para definir el flujo de ejecución.
- **Motor de Ejecución:** Al presionar "Ejecutar Secuencia", el software recorre el grafo de nodos, enviando los comandos Seriales correspondientes al Arduino en el orden y con los tiempos establecidos.

## 🛠️ Requisitos e Instalación

### Hardware
- Arduino (ej: Uno, Nano, Mega).
- 2x Módulos PCA9685 (direccionados a 0x40 y 0x43).
- Servomotores.
- Fuente de alimentación externa para los servos (el Arduino no puede alimentarlos por sí solo).

### Software
1. **Arduino IDE:**
   - Instalar la librería `Adafruit PWM Servo Driver Library` desde el Gestor de Librerías.
   - Cargar el sketch `servo_controller.ino` en la placa.
2. **Python 3.x:**
   - Crear un entorno virtual (opcional pero recomendado): `python -m venv .venv` y activarlo.
   - Instalar dependencias:
     ```bash
     pip install customtkinter pyserial
     ```

## 🚀 Cómo Iniciar
1. Conecta el Arduino vía USB.
2. Asegúrate de ejecutar el calibrador primero para ajustar los motores y evitar daños mecánicos:
   ```bash
   python python_app/main.py
   ```
3. Crea tus "Acciones" en la pestaña de Acciones Dinámicas.
4. Cierra el calibrador y abre el secuenciador para animar tu robot:
   ```bash
   python python_app/node_sequencer.py
   ```

---

## ☁️ Guía: Cómo subir este proyecto a GitHub

Para respaldar tu código en la nube (GitHub), sigue exactamente estos pasos en tu terminal (asegúrate de estar ubicado en la carpeta `/home/ubuntu/TESIS`):

### Paso 1: Inicializar Git (Si no lo has hecho)
```bash
git init
```

### Paso 2: Ignorar archivos innecesarios
Antes de subir código, es importantísimo ignorar carpetas pesadas o temporales como los entornos virtuales de Python (`.venv`) y los archivos en caché. Crea un archivo llamado `.gitignore` y añade lo siguiente:
```bash
echo ".venv/" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

### Paso 3: Agregar todo el código y crear el Commit
Se empaqueta todo el código actual junto con un mensaje de versión.
```bash
git add .
git commit -m "Primer commit: Framework de calibración y secuenciación de servomotores"
```

### Paso 4: Conectar con tu Repositorio en GitHub
1. Entra a [GitHub](https://github.com/) e inicia sesión.
2. Arriba a la derecha, haz clic en el botón `+` y selecciona **New repository**.
3. Ponle un nombre (ej. `tesis-framework-robotica`), déjalo como Público o Privado y **NO** marques la casilla "Add a README file" (porque ya acabamos de crear uno).
4. Dale a **Create repository**.

Copia la URL que te dará GitHub en la siguiente pantalla (se verá algo como `https://github.com/TuUsuario/tesis-framework-robotica.git`).

En tu terminal, enlaza tu código con GitHub usando la URL copiada:
```bash
# Cambia la URL por la de tu repositorio real
git remote add origin https://github.com/TuUsuario/tu-repositorio.git
```

### Paso 5: Subir los archivos (Push)
Finalmente, sube la rama principal (`main` o `master`) a la nube:
```bash
git branch -M main
git push -u origin main
```
*(Es probable que te pida tu usuario y contraseña de GitHub; hoy en día GitHub usa "Personal Access Tokens" en lugar de la contraseña regular, así que asegúrate de generar uno desde Settings -> Developer Settings -> Personal access tokens si te lo pide).*
