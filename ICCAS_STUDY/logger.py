import csv
import json
import os
import time
import numpy as np
from datetime import datetime
import cv2


class StudyLogger:
    """
    Records every frame of an ICCAS trial to a CSV file.
    Saves a JSON summary at the end of the trial.
    """

    CSV_HEADERS = [
        "timestamp", "elapsed_time_ms", "trial_id", "repetition_number",
        "participant_id", "condition", "scenario",
        "expected_state", "current_state", "previous_state", "state_transition",
        "source_of_decision", "ambiguous_case",
        "mediapipe_face_detected", "mediapipe_is_looking", "mediapipe_pitch", "mediapipe_yaw",
        "vlm_robot_state", "vlm_person_present", "vlm_attention_target", "vlm_interaction_availability",
        "vlm_visible_objects", "vlm_scene_summary", "vlm_confidence",
        "mediapipe_inference_ms", "vlm_inference_ms", "sm_update_ms",
        "audio_state", "event_note", "snapshot_path",
        "neck_pitch", "neck_pan", "upper_eyelids", "lower_eyelids", "jaw_position",
        "motor_command_count",
    ]

    def __init__(
        self,
        subject_id: str = "00",
        condition:  str = "A",
        scenario:   str = "1",
        trial_id:   str = "T1",
        repetition: int = 1,
        log_dir:    str = "logs",
    ):
        self.subject_id = subject_id
        self.condition  = condition
        self.scenario   = scenario
        self.trial_id   = trial_id
        self.repetition = repetition
        self.log_dir    = log_dir
        self.snapshots_dir = os.path.join(log_dir, "snapshots")

        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(self.snapshots_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"subj{subject_id}_cond{condition}_scen{scenario}_{trial_id}_rep{repetition}_{ts}"
        self.csv_path     = os.path.join(log_dir, f"{base}.csv")
        self.summary_path = os.path.join(log_dir, f"{base}_summary.json")

        self.start_time = time.time()

        # ── Internal tracking ─────────────────────────────────────────────
        self._prev_state:        str   = "sleeping"
        self._state_sequence:    list  = []
        self._state_entry_times: dict  = {}       # state → first entry timestamp
        self._detection_latencies: list = []      # ms from face_detected to person_detected
        self._action_latencies:    list = []      # ms from state decision to action
        self._face_first_seen:   float = 0.0     # for detection latency measurement
        self._state_decision_time: float = 0.0

        # ── Write CSV header ──────────────────────────────────────────────
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self.CSV_HEADERS)

        print(f"[Logger] CSV → {self.csv_path}")

    # ─────────────────────────── Frame logging ───────────────────────────

    def log_event(
        self,
        current_state:   str,
        vision_results:  dict,
        vlm_result:      dict,
        audio_state:     str,
        motor_snapshot:  dict,
        motor_cmd_count: int,
        event_note:      str = "",
        expected_state:  str | None = None,
        sm_metrics:      dict | None = None,
        perf_metrics:    dict | None = None,
        frame:           np.ndarray | None = None,
    ):
        """Log one frame. Call this every iteration of the experiment loop."""
        now      = time.time()
        ts_str   = datetime.fromtimestamp(now).strftime("%H:%M:%S.%f")[:-3]
        elapsed  = int((now - self.start_time) * 1000)
        sm = sm_metrics or {}
        perf = perf_metrics or {}

        # ── State change detection ────────────────────────────────────────
        state_transition = (current_state != self._prev_state)
        snapshot_path = ""
        if state_transition:
            self._on_state_change(current_state, now)
            if frame is not None:
                fname = f"snap_{elapsed}_{current_state}.jpg"
                snapshot_path = os.path.join(self.snapshots_dir, fname)
                cv2.imwrite(snapshot_path, frame)
        self._prev_state = current_state

        if expected_state is None:
            expected_state = current_state

        # ── Detection latency tracking ────────────────────────────────────
        face_detected = vision_results.get("face_detected", False)
        if face_detected and self._face_first_seen == 0.0:
            self._face_first_seen = now
        if not face_detected:
            self._face_first_seen = 0.0
        if current_state == "person_detected" and self._face_first_seen > 0.0 and state_transition:
            self._detection_latencies.append(int((now - self._face_first_seen) * 1000))

        # ── VLM fields (safe extraction) ──────────────────────────────────
        vlm = vlm_result or {}
        vlm_objects_str = json.dumps(vlm.get("visible_objects", []))

        row = [
            ts_str,
            elapsed,
            self.trial_id,
            self.repetition,
            self.subject_id,
            self.condition,
            self.scenario,
            expected_state,
            current_state,
            sm.get("previous_state", ""),
            state_transition,
            sm.get("source_of_decision", ""),
            sm.get("ambiguous_case", False),
            face_detected,
            vision_results.get("is_looking",   False),
            round(vision_results.get("pitch",  0.0), 2),
            round(vision_results.get("yaw",    0.0), 2),
            vlm.get("robot_state",              "unknown"),
            vlm.get("person_present",           None),
            vlm.get("attention_target",         "unknown"),
            vlm.get("interaction_availability", "unknown"),
            vlm_objects_str,
            vlm.get("scene_summary",            ""),
            vlm.get("confidence",               "unknown"),
            perf.get("mediapipe_inference_ms",  0),
            vlm.get("inference_time_ms",        0),
            perf.get("sm_update_ms",            0),
            audio_state,
            event_note,
            snapshot_path,
            motor_snapshot.get("neck_pitch",    0),
            motor_snapshot.get("neck_pan",      0),
            motor_snapshot.get("upper_eyelids", 0),
            motor_snapshot.get("lower_eyelids", 0),
            motor_snapshot.get("jaw_position",  0),
            motor_cmd_count,
        ]

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

    # ─────────────────────────── State tracking ──────────────────────────

    def _on_state_change(self, new_state: str, now: float):
        if new_state not in self._state_sequence:
            self._state_sequence.append(new_state)
        if new_state not in self._state_entry_times:
            self._state_entry_times[new_state] = datetime.fromtimestamp(now).strftime(
                "%H:%M:%S.%f"
            )[:-3]

    # ─────────────────────────── Summary ─────────────────────────────────

    def save_summary(self, sm_metrics: dict | None = None, notes: str = ""):
        """
        Write JSON summary. Pass sm_metrics from StateMachine.get_metrics().
        """
        sm = sm_metrics or {}
        ev = sm.get("event_times", {})

        mean_det = (
            round(sum(self._detection_latencies) / len(self._detection_latencies))
            if self._detection_latencies else None
        )
        mean_act = (
            round(sum(self._action_latencies) / len(self._action_latencies))
            if self._action_latencies else None
        )

        summary = {
            "participant_id":             self.subject_id,
            "condition":                  self.condition,
            "scenario":                   self.scenario,
            "trial_id":                   self.trial_id,
            "repetition_number":          self.repetition,
            "trial_start_time":           datetime.fromtimestamp(self.start_time).isoformat(),
            "person_detected_time":       ev.get("person_detected_time"),
            "attention_detected_time":    ev.get("attention_detected_time"),
            "speech_start_time":          ev.get("speech_start_time"),
            "distraction_detected_time":  ev.get("distraction_detected_time"),
            "pause_triggered_time":       ev.get("pause_triggered_time"),
            "attention_recovered_time":   ev.get("attention_recovered_time"),
            "resume_triggered_time":      ev.get("resume_triggered_time"),
            "waiting_timeout_time":       ev.get("waiting_timeout_time"),
            "sleeping_return_time":       ev.get("sleeping_return_time"),
            "trial_end_time":             datetime.now().isoformat(),
            "state_sequence":             self._state_sequence,
            "number_of_state_transitions": sm.get("n_transitions", 0),
            "number_of_attention_losses": sm.get("n_attention_losses", 0),
            "number_of_resumes":          sm.get("n_resumes", 0),
            "ambiguous_cases_count":      0, # Can be calculated from CSV or tracked here
            "motor_commands_count":       0,   # filled by main.py
            "mean_detection_latency_ms":  mean_det,
            "mean_action_latency_ms":     mean_act,
            "notes":                      notes,
        }

        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)

        print(f"[Logger] Summary → {self.summary_path}")
        return summary
