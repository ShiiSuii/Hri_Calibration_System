import time
from datetime import datetime
from config import THRESHOLDS

class StateMachine:
    """
    HRI State Machine for ICCAS Study.
    """

    ABSENCE_IMMUNE = {"sleeping", "finished"}

    def __init__(self, condition="B"):
        self.state = "sleeping"
        self.previous_state = "sleeping"
        self.condition = condition
        self.source_of_decision = "initial"
        self.ambiguous_case = False

        # ── Internal timers ──────────────────────────────────────────────
        self.absence_start_time      = 0.0
        self.distraction_start_time  = 0.0
        self.resume_start_time       = 0.0
        self.attention_start_time    = 0.0
        self.waiting_start_time      = 0.0
        
        # Timing aliases from config
        self.distraction_threshold       = THRESHOLDS["distraction"]
        self.resume_threshold            = THRESHOLDS["resume"]
        self.absence_threshold           = THRESHOLDS["absence"]
        self.attention_confirm_threshold = THRESHOLDS["attention_confirm"]
        self.waiting_timeout_threshold   = THRESHOLDS["waiting_timeout"]

        # ── Script-sequence flags ─────────────────────────────────────────
        self.main_response_started   = False
        self.main_response_paused    = False
        self.main_response_finished  = False

        # ── Session metrics ───────────────────────────────────────────────
        self.n_transitions        = 0
        self.n_attention_losses   = 0
        self.n_resumes            = 0
        self.disengagement_timeout = False

        # ── Event timestamps (set once, first occurrence) ─────────────────
        self.event_times = {
            "person_detected_time":      None,
            "attention_detected_time":   None,
            "speech_start_time":         None,
            "distraction_detected_time": None,
            "pause_triggered_time":      None,
            "attention_recovered_time":  None,
            "resume_triggered_time":     None,
            "waiting_timeout_time":      None,
            "sleeping_return_time":      None,
        }

        # ── Pending audio request ─────────────────────────────────────────
        self.pending_audio = None

        # ── Blink request flag (read by main.py) ──────────────────────────
        self.blink_requested = False

    # ─────────────────────────── Helpers ─────────────────────────────────

    @staticmethod
    def _now_str():
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def _set_event(self, key):
        if self.event_times.get(key) is None:
            self.event_times[key] = self._now_str()

    def _transition_to(self, new_state, source="SM"):
        self.previous_state = self.state
        self.state = new_state
        self.source_of_decision = source
        self.n_transitions += 1

    # ─────────────────────────── Public API ──────────────────────────────

    def trigger_user_question(self):
        """Called by main.py when experimenter presses 's'."""
        if self.state == "attention_detected":
            self.pending_audio = "respuesta"
            self._transition_to("interacting", source="experimenter")
            self.main_response_started = True
            self._set_event("speech_start_time")

    def update(self, vision_results: dict, vlm_result: dict, speech_status: dict):
        """
        Main update called every frame.

        Args:
            vision_results: dict from VisionPerception.estimate_attention()
            vlm_result:     dict from VLMWorker.get_latest_result()
            speech_status:  dict {is_playing, current_track, finished_track}

        Returns:
            (current_state: str, event_note: str)
        """
        current_time = time.time()
        event_note   = ""

        face_detected = vision_results.get("face_detected", False)

        # ── Fuse MediaPipe + VLM attention ───────────────────────────────
        is_looking = vision_results.get("is_looking", False)
        self.ambiguous_case = False
        
        if vlm_result:
            vlm_looking = None
            attn = vlm_result.get("attention_target", "unknown")
            if attn in ("phone", "elsewhere"):
                vlm_looking = False
            elif attn == "robot":
                vlm_looking = True
            
            # Detect ambiguity
            if vlm_looking is not None and vlm_looking != is_looking:
                self.ambiguous_case = True
            
            # For B condition, VLM has a weight in the decision
            if vlm_looking is not None:
                is_looking = vlm_looking

        # ── Absence tracking ──────────────────────────────────────────────
        if not face_detected:
            if self.absence_start_time == 0.0:
                self.absence_start_time = current_time
        else:
            self.absence_start_time = 0.0

        absence_elapsed = (current_time - self.absence_start_time) if self.absence_start_time > 0 else 0.0
        if absence_elapsed >= self.absence_threshold and self.state not in self.ABSENCE_IMMUNE:
            if self.state != "finished":
                self._transition_to("finished", source="MediaPipe_absence")
                self.pending_audio = "despedida"
                self.absence_start_time = 0.0
                event_note = "User absent → finished"
                return self.state, event_note

        # ── State machine ─────────────────────────────────────────────────

        if self.state == "sleeping":
            if face_detected:
                self._transition_to("person_detected", source="MediaPipe")
                self.pending_audio = "apertura"
                self.blink_requested = True
                self._set_event("person_detected_time")
                event_note = "Face detected → waking up"

        elif self.state == "person_detected":
            if is_looking:
                if self.attention_start_time == 0.0:
                    self.attention_start_time = current_time
                elif (current_time - self.attention_start_time) >= self.attention_confirm_threshold:
                    self._transition_to("attention_detected", source="MediaPipe_attention")
                    self.pending_audio = "disponibilidad"
                    self._set_event("attention_detected_time")
                    self.attention_start_time = 0.0
                    event_note = "Attention stable → attention_detected"
            else:
                self.attention_start_time = 0.0

        elif self.state == "attention_detected":
            # Waiting for experimenter to press 's'
            pass

        elif self.state == "interacting":
            # Condition B: monitor distraction
            if self.condition == "B" and not self.main_response_finished:
                if not is_looking:
                    if self.distraction_start_time == 0.0:
                        self.distraction_start_time = current_time
                    elif (current_time - self.distraction_start_time) >= self.distraction_threshold:
                        source = "VLM" if self.ambiguous_case else "MediaPipe"
                        self._transition_to("user_distracted", source=source)
                        self.n_attention_losses += 1
                        self._set_event("distraction_detected_time")
                        self.distraction_start_time = 0.0
                        event_note = f"Distraction detected ({source}) → user_distracted"
                else:
                    self.distraction_start_time = 0.0

            # Natural end of respuesta
            if speech_status.get("finished_track") == "respuesta":
                self.main_response_finished = True
                self.pending_audio = "cierre"
                event_note = "Response finished → playing cierre"

            # After cierre, move to finished
            if speech_status.get("finished_track") == "cierre":
                self._transition_to("finished")
                self.pending_audio = "despedida"
                event_note = "Cierre done → finished"

        elif self.state == "user_distracted":
            # Transient state: immediately go to waiting
            self._transition_to("waiting", source="timer")
            self.pending_audio = "pausa"
            self.main_response_paused = True
            self.waiting_start_time = current_time
            self._set_event("pause_triggered_time")
            event_note = "→ waiting"

        elif self.state == "waiting":
            waiting_elapsed = current_time - self.waiting_start_time

            # Disengagement timeout
            if waiting_elapsed >= self.waiting_timeout_threshold:
                self._transition_to("sleeping", source="waiting_timeout")
                self.pending_audio = "desengagement"
                self.disengagement_timeout = True
                self.absence_start_time = 0.0
                self._set_event("waiting_timeout_time")
                self._set_event("sleeping_return_time")
                event_note = "Disengagement timeout → sleeping"

            elif is_looking:
                if self.resume_start_time == 0.0:
                    self.resume_start_time = current_time
                elif (current_time - self.resume_start_time) >= self.resume_threshold:
                    source = "VLM" if self.ambiguous_case else "MediaPipe"
                    self._transition_to("resume_interaction", source=source)
                    self.pending_audio = "reanudacion"
                    self.n_resumes += 1
                    self.blink_requested = True
                    self._set_event("attention_recovered_time")
                    self._set_event("resume_triggered_time")
                    self.resume_start_time = 0.0
                    event_note = f"Attention regained ({source}) → resume_interaction"
            else:
                self.resume_start_time = 0.0

        elif self.state == "resume_interaction":
            if speech_status.get("finished_track") == "reanudacion":
                self._transition_to("interacting", source="audio_done")
                self.pending_audio = "respuesta"
                self.main_response_paused = False
                event_note = "Resuming explanation"

        elif self.state == "finished":
            if speech_status.get("finished_track") == "despedida":
                self._transition_to("sleeping", source="audio_done")
                self._set_event("sleeping_return_time")
                event_note = "Despedida done → sleeping"
            elif speech_status.get("finished_track") == "desengagement":
                # Already in sleeping, nothing to do
                pass

        return self.state, event_note

    def get_and_clear_audio(self):
        audio = self.pending_audio
        self.pending_audio = None
        return audio

    def get_and_clear_blink(self):
        b = self.blink_requested
        self.blink_requested = False
        return b

    def get_metrics(self):
        return {
            "n_transitions":       self.n_transitions,
            "n_attention_losses":  self.n_attention_losses,
            "n_resumes":           self.n_resumes,
            "disengagement_timeout": self.disengagement_timeout,
            "ambiguous_case":      self.ambiguous_case,
            "source_of_decision":  self.source_of_decision,
            "previous_state":      self.previous_state,
            "event_times":         self.event_times.copy(),
        }

    def reset(self):
        self.__init__(self.condition)
