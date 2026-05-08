import serial
import serial.tools.list_ports
import time
import threading
import random
import math
from config import MOTOR_SETTINGS, MOTOR_CHANNELS


class RobotController:
    """
    Controls the animatronic robot head via Arduino serial (115200 baud).
    Protocol: 'C<channel> P<pulse>\\n'
    
    Active channels:
        0  → Jaw
        6  → Lower eyelid left
        7  → Eye tilt right
        8  → Upper eyelid right
        9  → Lower eyelid right
        10 → Eye pan right (neutral only)
        11 → Upper eyelid left
        18 → Neck tilt (pitch)
        19 → Neck pan (fixed 375)

    Eye-rotation channels (4, 5, 7, 10) are set to neutral at startup
    and are NOT updated during the session (no active eye tracking).
    Blinking is the only expressive eye movement.
    """

    # ── Servo neutral/home positions ─────────────────────────────────────
    EYE_NEUTRAL = MOTOR_CHANNELS["eye_neutral"]

    # ── State pose dictionary ─────────────────────────────────────────────
    # Channels: 18=neck_tilt, 19=neck_pan, 11/8=upper lids, 9/6=lower lids, 0=jaw
    STATE_DICT = {
        "sleeping": {
            18: 500, 19: 375,
            11: 285, 9: 306, 8: 249, 6: 464,  # Eyelids closed
            0: 257
        },
        "person_detected": {
            18: 362, 19: 375,
            11: 325, 9: 270, 8: 307, 6: 430,  # Eyelids open
            0: 257
        },
        "attention_detected": {
            18: 350, 19: 375,
            11: 335, 9: 260, 8: 320, 6: 420,  # Eyelids wide open
            0: 257
        },
        "interacting": {
            18: 362, 19: 375,
            11: 325, 9: 270, 8: 307, 6: 430,
            0: 257
        },
        "user_distracted": {
            18: 390, 19: 375,
            11: 305, 9: 285, 8: 280, 6: 445,  # Semi-closed
            0: 257
        },
        "waiting": {
            18: 410, 19: 375,
            11: 285, 9: 306, 8: 249, 6: 464,  # Closed / resting
            0: 257
        },
        "resume_interaction": {
            18: 362, 19: 375,
            11: 325, 9: 270, 8: 307, 6: 430,
            0: 257
        },
        "finished": {
            18: 480, 19: 375,
            11: 285, 9: 306, 8: 249, 6: 464,  # Closing
            0: 257
        },
    }

    def __init__(self):
        self.ser = self._auto_connect()
        self.running = True
        self.motor_command_count = 0

        # ── Current and target positions ──────────────────────────────────
        self.current_positions = {
            18: 500, 19: 375,
            11: 285,  9: 306,  8: 249, 6: 464,
            0: 257
        }
        self.target_positions = self.current_positions.copy()

        # ── Interpolation speeds ──────────────────────────────────────────
        self.slow_speed   = MOTOR_SETTINGS["slow_speed"]
        self.normal_speed = MOTOR_SETTINGS["normal_speed"]
        self.current_speed = self.normal_speed

        # ── Idle / Auto-OFF tracking ──────────────────────────────────────
        self.last_target_change = {k: time.time() for k in self.current_positions}
        self.is_off = {k: False for k in self.current_positions}

        # ── State flags ───────────────────────────────────────────────────
        self.is_speaking  = False
        self.is_awake     = False
        self.is_blinking  = False
        self.blink_request = False   # Set True to trigger an expressive blink
        self.jaw_timer    = 0.0

        if not self.ser:
            print("[RobotControl] WARNING: Arduino not found. Running in simulated mode.")
        else:
            print(f"[RobotControl] Serial connected: {self.ser.port}")

        # ── Set eye-rotation channels to neutral once, then ignore them ───
        for ch, pulse in self.EYE_NEUTRAL.items():
            self._send_raw(ch, pulse)

        # ── Start background threads ──────────────────────────────────────
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

        self._blink_thread = threading.Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()

    # ─────────────────────────── Serial ──────────────────────────────────

    def _auto_connect(self):
        for p in serial.tools.list_ports.comports():
            if any(x in p.description or x in p.device for x in ("Arduino", "ACM", "USB")):
                try:
                    return serial.Serial(p.device, 115200, timeout=0.1)
                except Exception:
                    continue
        return None

    def _send_raw(self, channel: int, pulse: int):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(f"C{channel} P{int(pulse)}\n".encode())
                self.motor_command_count += 1
            except Exception:
                pass

    # ─────────────────────────── Background loops ────────────────────────

    def _update_loop(self):
        """50 Hz interpolation + jaw animation + Auto-OFF."""
        while self.running:
            now = time.time()

            # Coordination: if speaking, we inhibit other major motor updates to save current
            # However, we still allow neck movements for natural look if needed, 
            # but we'll prioritize jaw for now as requested.
            
            for chan, target in list(self.target_positions.items()):
                # Skip jaw when speaking (handled separately)
                if chan == 0 and self.is_speaking:
                    continue
                
                # USER REQ: "cuando este moviendo la mandibula no mueva los ojos"
                # If jaw is moving (speaking), we skip eyelids (channels 11, 9, 8, 6)
                if self.is_speaking and chan in (11, 9, 8, 6):
                    continue

                curr = self.current_positions[chan]
                if curr != target:
                    self.last_target_change[chan] = now
                    self.is_off[chan] = False
                    diff = target - curr
                    step = self.current_speed if abs(diff) > self.current_speed else abs(diff)
                    self.current_positions[chan] += step if diff > 0 else -step
                    self._send_raw(chan, self.current_positions[chan])
                else:
                    # Auto-OFF after 5s of no movement
                    if not self.is_off[chan] and (now - self.last_target_change[chan]) > 5.0:
                        self._send_raw(chan, 0)
                        self.is_off[chan] = True

            # Jaw sinusoidal animation while speaking
            if self.is_speaking:
                self.jaw_timer += 0.02
                jaw_pos = 257 + int(15 * (1 + math.sin(self.jaw_timer * 15)))
                self._send_raw(0, jaw_pos)
            else:
                self.jaw_timer = 0.0

            time.sleep(0.02)

    def _blink_loop(self):
        """Natural sporadic blinking + expressive blink on request."""
        # Eyelid closed/open positions
        CLOSED = {11: 285, 9: 306, 8: 249, 6: 464}

        while self.running:
            if not self.is_awake:
                time.sleep(0.5)
                continue

            # Expressive blink requested by state machine
            if self.blink_request:
                self.blink_request = False
                self._do_blink(CLOSED)
                continue

            # Natural random blink every 3–7 seconds
            wait = random.uniform(3.0, 7.0)
            # Poll blink_request while waiting
            elapsed = 0.0
            while elapsed < wait and self.running and self.is_awake:
                if self.blink_request:
                    break
                time.sleep(0.1)
                elapsed += 0.1

            if self.blink_request:
                self.blink_request = False
                self._do_blink(CLOSED)
            else:
                self._do_blink(CLOSED)

    def _do_blink(self, closed_pos: dict):
        """Execute a single blink cycle."""
        if not self.is_awake:
            return
        self.is_blinking = True

        # Save current eyelid targets
        orig = {k: self.target_positions.get(k, closed_pos[k]) for k in closed_pos}

        # Close
        for k, v in closed_pos.items():
            self._send_raw(k, v)
        time.sleep(0.12)

        # Open
        for k, v in orig.items():
            self._send_raw(k, v)

        self.is_blinking = False

    # ─────────────────────────── Public API ──────────────────────────────

    def apply_state(self, state_name: str):
        """Apply a named pose. Uses slow speed for sleeping/detected transitions."""
        if state_name not in self.STATE_DICT:
            return
        print(f"[RobotControl] Applying state: {state_name}")
        self.is_awake = (state_name not in ("sleeping", "finished"))

        if state_name in ("sleeping", "person_detected", "finished"):
            self.current_speed = self.slow_speed
        else:
            self.current_speed = self.normal_speed

        new_pose = self.STATE_DICT[state_name].copy()
        
        # USER REQ: "modo de cuando deja de ver a la persona que se vuelve a la posicion dormido, hacer que sea sin mover la mandibula"
        if state_name == "sleeping":
            if 0 in new_pose:
                # Keep current jaw position instead of moving to neutral
                new_pose[0] = self.current_positions.get(0, 257)

        self.target_positions.update(new_pose)

    def trigger_blink(self):
        """Request an expressive blink (e.g. on wake-up or resume)."""
        self.blink_request = True

    def is_interpolating(self) -> bool:
        for chan, target in self.target_positions.items():
            if chan == 0 and self.is_speaking:
                continue
            if abs(self.current_positions[chan] - target) > 1:
                return True
        return False

    def set_speaking(self, status: bool):
        self.is_speaking = status
        if not status:
            self.jaw_timer = 0.0

    def get_motor_snapshot(self) -> dict:
        """Return current logical motor positions for logging."""
        return {
            "neck_pitch":    self.current_positions.get(18, 0),
            "neck_pan":      self.current_positions.get(19, 0),
            "upper_eyelids": round((self.current_positions.get(11, 0) +
                                    self.current_positions.get(8, 0)) / 2),
            "lower_eyelids": round((self.current_positions.get(9, 0) +
                                    self.current_positions.get(6, 0)) / 2),
            "jaw_position":  self.current_positions.get(0, 0),
        }

    def close(self):
        self.apply_state("sleeping")
        start = time.time()
        while self.is_interpolating() and (time.time() - start) < 5.0:
            time.sleep(0.1)
        self.running = False
        time.sleep(0.3)
        if self.ser and self.ser.is_open:
            self.ser.close()
