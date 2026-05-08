# Estudio ICCAS: Guía de Protocolo y Funcionamiento del Sistema

Este documento describe el funcionamiento técnico y el protocolo experimental para el estudio de interacción humano-robot guiada por estados sociales.

## 1. Objetivo del Estudio
Evaluar si una arquitectura social-aware que regula habla y expresividad según la atención visual del usuario produce una interacción más coherente que un sistema baseline sin regulación atencional.

## 2. Configuración Experimental
- **Participantes:** 10 participantes voluntarios.
- **Diseño:** Within-subject (cada participante realiza ambas condiciones).
- **Condiciones:**
    - **Condición A (Baseline):** El robot detecta presencia y responde, pero no reacciona a la distracción del usuario.
    - **Condición B (Social-Aware):** El robot pausa el habla y adopta una postura de espera si el usuario se distrae, y reanuda cuando recupera la atención.
- **Escenarios:**
    - **Escenario 1 (Continuo):** Interacción fluida sin interrupciones.
    - **Escenario 2 (Interrumpido):** El participante desvía la mirada o mira su celular durante la respuesta del robot.

## 3. Guion del Robot (Audios)
El sistema utiliza 7 bloques de audio pre-generados para garantizar consistencia:
1. **Apertura:** "Hola. Estoy listo para conversar."
2. **Disponibilidad:** "Te escucho."
3. **Respuesta Principal:** Explicación sobre IA (Pausable en Condición B).
4. **Pausa (Solo B):** "Te espero."
5. **Reanudación (Solo B):** "Continúo."
6. **Cierre:** "Eso es, de forma breve, la inteligencia artificial."
7. **Despedida:** "Hasta luego."

## 4. Paso a Paso del Experimento

### Preparación
1. Ejecutar `python3 main.py`.
2. Ingresar ID del Participante y seleccionar Condición (A/B) y Escenario (1/2).
3. Presionar **START EXPERIMENT**. El robot irá a posición `sleeping`.

### Fase de Interacción
1. **Detección:** El participante entra al área. MediaPipe detecta presencia. El robot despierta lentamente e indica **Apertura**.
2. **Atención:** Cuando el sistema confirma atención estable, el robot indica **Disponibilidad**.
3. **Pregunta:** El participante dice: *“Buen día. ¿Podés explicarme brevemente qué es la inteligencia artificial?”*. 
4. **Respuesta:** El investigador presiona la tecla **'s'** en la ventana de video para disparar la **Respuesta Principal**. *Nota: Este es un trigger experimental controlado para asegurar sincronización y repetibilidad en la toma de datos.*
5. **Dinámica (Escenario 2):**
    - En **Condición B**, si el participante mira el celular (>2.0s), el robot dice **Pausa**. Durante el estado `waiting`, el robot pausa el audio, mantiene una postura de espera y no retoma hasta recuperar atención estable. Al volver a mirar (>0.8s), dice **Reanudación** y sigue.
    - En **Condición A**, el robot ignora la distracción.
6. **Cierre:** Al terminar la explicación, el robot da el **Cierre**.
7. **Salida:** Cuando el participante se retira, el robot da la **Despedida** y vuelve a `sleeping`.

Al final de cada condición, el participante completará un cuestionario en **Google Forms**.

## 5. Arquitectura Técnica
- **Percepción Híbrida:** 
    - **MediaPipe (Módulo Principal):** Procesamiento online (30 fps) para seguimiento facial y pose de cabeza.
    - **SmolVLM-500M (Validador Semántico):** Clasificador de contexto a baja frecuencia en background para clasificar estados: `mirando al robot`, `mirando celular`, `mirando fuera`, `sin persona`.
- **Control Motor:** Interpolación lineal para movimientos suaves, parpadeo estocástico y sincronización de mandíbula con el audio.
- **Thresholds del Sistema:**
    - **Atención estable para interactuar:** 0.8 s
    - **Distracción sostenida para pausar:** 2.0 s
    - **Ausencia para volver a sleeping:** 4.5 s

## 6. Registro de Datos (Data Logging)
El sistema genera un log automático con las siguientes métricas para el paper:
- `participant_id`, `condition`, `scenario`
- `trial_start_time`, `trial_end_time`
- `person_detected_time`, `attention_detected_time`
- `speech_start_time`
- `distraction_detected_time`, `pause_triggered_time`
- `attention_recovered_time`, `resume_triggered_time`
- `state_sequence`
- `motor_commands_log`
