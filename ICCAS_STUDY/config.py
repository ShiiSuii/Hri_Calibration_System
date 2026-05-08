"""
ICCAS Study Configuration Management
Centralized repository for thresholds, motor limits, and experimental scripts.
"""

# ── TIMING THRESHOLDS (seconds) ──────────────────────────────────────────
THRESHOLDS = {
    "distraction":        2.0,   # Time looking away before pausing
    "resume":             0.8,   # Time looking back before resuming
    "absence":            4.5,   # Time without face before finishing
    "attention_confirm":  0.8,   # Time looking before waking up fully
    "waiting_timeout":    5.0,   # Time in waiting before returning to sleeping
    "attention_pitch_limit": 30.0, # Degrees
    "attention_yaw_limit":   30.0, # Degrees
}

# ── MOTOR LIMITS & SETTINGS ──────────────────────────────────────────────
MOTOR_SETTINGS = {
    "slow_speed":   2,
    "normal_speed": 10,
    "auto_off_delay": 5.0,  # Seconds of inactivity before turning off servo
}

MOTOR_CHANNELS = {
    "jaw":           0,
    "neck_pitch":    18,
    "neck_pan":      19,
    "l_eye_lid_up":  11,
    "l_eye_lid_lo":  9,
    "r_eye_lid_up":  8,
    "r_eye_lid_lo":  6,
    "eye_neutral": {
        4: 327, 
        10: 300, 
        5: 280, 
        7: 367
    }
}

# ── VLM SETTINGS ─────────────────────────────────────────────────────────
VLM_SETTINGS = {
    "model_id": "moondream",
    "host":     "http://localhost:11434",
    "timeout":  15,
    "analysis_interval": 2.5,  # Minimum seconds between VLM calls
}

# ── EXPERIMENTAL SCRIPT ──────────────────────────────────────────────────
# This structure defines the tracks and expected flow for the study.
EXPERIMENTAL_SCRIPT = {
    "tracks": {
        "apertura":       "Greetings and initial engagement",
        "disponibilidad": "Checking if user is ready",
        "respuesta":      "Main educational/interaction content",
        "pausa":          "Brief pause due to distraction",
        "reanudacion":    "Resuming interaction",
        "cierre":         "Concluding the interaction",
        "despedida":      "Final goodbye",
        "desengagement":  "Returning to sleep after timeout",
    },
    "scenarios": {
        "1": "Informative interaction",
        "2": "Social interaction",
    }
}
