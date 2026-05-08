"""
ICCAS Research Dashboard — main.py
Canvas-Tkinter based HRI experiment controller.

Hotkeys:
    s → Trigger experimenter question (attention_detected → interacting)
    q → Stop experiment
"""

import tkinter as tk
import threading
import time
import queue

import cv2
import PIL.Image
import PIL.ImageTk

from logger        import StudyLogger
from vision        import VisionPerception
from state_machine import StateMachine
from robot_control import RobotController
from speech        import SpeechEngine
from vlm_worker    import VLMWorker


# ── Colour palette ─────────────────────────────────────────────────────────
BG          = "#0F1117"
PANEL_BG    = "#181C24"
BORDER      = "#2A2F3E"
TEXT_PRI    = "#E8ECF4"
TEXT_SEC    = "#8A94A8"
ACCENT      = "#4C6EF5"

STATE_COLORS = {
    "sleeping":           "#37474F",
    "person_detected":    "#1565C0",
    "attention_detected": "#00838F",
    "interacting":        "#2E7D32",
    "user_distracted":    "#BF360C",
    "waiting":            "#E65100",
    "resume_interaction": "#558B2F",
    "finished":           "#6A1A1A",
}

FONT_TITLE  = ("Helvetica Neue", 14, "bold")
FONT_LABEL  = ("Helvetica Neue", 10)
FONT_VALUE  = ("Helvetica Neue", 10, "bold")
FONT_STATE  = ("Helvetica Neue", 16, "bold")
FONT_MONO   = ("Courier", 9)


class ICCAS_Dashboard:

    PANEL_W = 380
    PANEL_H = 760
    VIDEO_W = 640
    VIDEO_H = 480

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ICCAS Research Dashboard")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        win_w = self.PANEL_W + self.VIDEO_W + 30
        win_h = self.PANEL_H + 20
        self.root.geometry(f"{win_w}x{win_h}")

        # ── Shared state dict (thread → UI) ──────────────────────────────
        self._ui_state = {
            "state":        "sleeping",
            "face":         False,
            "looking":      False,
            "pitch":        0.0,
            "yaw":          0.0,
            "vlm":          {},
            "audio_state":  "idle",
            "frame_img":    None,
        }
        self._ui_lock = threading.Lock()

        # ── Experiment control flags ──────────────────────────────────────
        self.running          = False
        self.trigger_question = False

        # ── VLM (started once, persists across experiments) ───────────────
        self.vlm = VLMWorker()

        # ── Build UI ──────────────────────────────────────────────────────
        self._build_left_panel()
        self._build_right_panel()
        self._bind_keys()

        # ── Start UI refresh loop ─────────────────────────────────────────
        self.root.after(50, self._refresh_ui)

    # ──────────────────────────── UI Build ────────────────────────────────

    def _build_left_panel(self):
        self.left = tk.Frame(self.root, bg=BG, width=self.PANEL_W)
        self.left.pack(side="left", fill="y", padx=(10, 5), pady=10)
        self.left.pack_propagate(False)

        # ── Dashboard canvas ──────────────────────────────────────────────
        self.dash = tk.Canvas(
            self.left,
            width=self.PANEL_W - 10,
            height=560,
            bg=PANEL_BG,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.dash.pack(fill="x")

        # ── Config & controls frame below canvas ──────────────────────────
        ctrl = tk.Frame(self.left, bg=BG)
        ctrl.pack(fill="x", pady=(8, 0))

        def lbl(parent, text, col=TEXT_SEC):
            tk.Label(parent, text=text, bg=BG, fg=col,
                     font=FONT_LABEL).pack(anchor="w")

        def entry_row(parent, label, var, values=None, width=18):
            row = tk.Frame(parent, bg=BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=BG, fg=TEXT_SEC,
                     font=FONT_LABEL, width=10, anchor="w").pack(side="left")
            if values:
                cb = tk.OptionMenu(row, var, *values)
                cb.config(bg=PANEL_BG, fg=TEXT_PRI, font=FONT_LABEL,
                          activebackground=BORDER, bd=0, highlightthickness=0,
                          width=width - 10)
                cb["menu"].config(bg=PANEL_BG, fg=TEXT_PRI, font=FONT_LABEL)
                cb.pack(side="left", fill="x", expand=True)
            else:
                e = tk.Entry(row, textvariable=var, font=FONT_LABEL,
                             bg=PANEL_BG, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                             bd=0, highlightthickness=1,
                             highlightbackground=BORDER, width=width)
                e.pack(side="left", fill="x", expand=True)

        self.subj_id    = tk.StringVar(value="01")
        self.condition  = tk.StringVar(value="B")
        self.scenario   = tk.StringVar(value="2")
        self.trial_id   = tk.StringVar(value="T1")
        self.repetition = tk.IntVar(value=1)
        self.cam_index  = tk.StringVar(value="0")

        entry_row(ctrl, "Subject ID:",  self.subj_id)
        entry_row(ctrl, "Condition:",   self.condition,  ["A", "B"])
        entry_row(ctrl, "Scenario:",    self.scenario,   ["1", "2"])
        entry_row(ctrl, "Trial ID:",    self.trial_id)
        entry_row(ctrl, "Repetition:",  self.repetition)
        entry_row(ctrl, "Camera:",      self.cam_index,  ["0", "1", "2", "3"])

        btn_frame = tk.Frame(ctrl, bg=BG)
        btn_frame.pack(fill="x", pady=(8, 0))

        self.start_btn = tk.Button(
            btn_frame, text="▶  START EXPERIMENT",
            command=self.start_experiment,
            bg=ACCENT, fg="white", font=FONT_VALUE,
            activebackground="#6C8EF7", activeforeground="white",
            bd=0, padx=12, pady=7, cursor="hand2",
        )
        self.start_btn.pack(fill="x", pady=(0, 4))

        self.stop_btn = tk.Button(
            btn_frame, text="■  STOP",
            command=self.stop_experiment,
            bg="#3A1A1A", fg="#EF9A9A", font=FONT_VALUE,
            activebackground="#5A2A2A", activeforeground="white",
            bd=0, padx=12, pady=6, cursor="hand2",
            state="disabled",
        )
        self.stop_btn.pack(fill="x")

        tk.Label(
            ctrl,
            text="Hotkeys:  s → Trigger    q → Stop",
            bg=BG, fg=TEXT_SEC, font=("Courier", 9),
        ).pack(pady=(8, 0))

    def _build_right_panel(self):
        self.right = tk.Frame(self.root, bg=BG)
        self.right.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        self.video_canvas = tk.Canvas(
            self.right,
            width=self.VIDEO_W,
            height=self.VIDEO_H,
            bg="#000000",
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.video_canvas.pack()

        # Status bar below video
        self.status_bar = tk.Label(
            self.right,
            text="Ready — configure parameters and press START",
            bg=PANEL_BG, fg=TEXT_SEC, font=FONT_MONO,
            anchor="w", padx=8, pady=4,
        )
        self.status_bar.pack(fill="x", pady=(4, 0))

    def _bind_keys(self):
        self.root.bind("<s>", lambda e: self._on_s())
        self.root.bind("<q>", lambda e: self._on_q())

    # ──────────────────────────── Key handlers ────────────────────────────

    def _on_s(self):
        if self.running:
            print("[UI] 's' pressed — triggering question")
            self.trigger_question = True

    def _on_q(self):
        if self.running:
            print("[UI] 'q' pressed — stopping")
            self.stop_experiment()

    # ──────────────────────────── Experiment control ──────────────────────

    def start_experiment(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.running          = True
        self.trigger_question = False

        t = threading.Thread(target=self._experiment_loop, daemon=True)
        t.start()

    def stop_experiment(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    # ──────────────────────────── Experiment loop ─────────────────────────

    def _experiment_loop(self):
        sid   = self.subj_id.get()
        cond  = self.condition.get()
        scen  = self.scenario.get()
        tid   = self.trial_id.get()
        rep   = self.repetition.get()
        cam   = int(self.cam_index.get())

        logger  = StudyLogger(subject_id=sid, condition=cond, scenario=scen, trial_id=tid, repetition=rep)
        robot   = RobotController()
        vision  = VisionPerception(camera_index=cam)
        speech  = SpeechEngine()
        sm      = StateMachine(condition=cond)

        speech.generate_all()
        robot.apply_state("sleeping")

        vlm_timer          = 0.0
        pending_audio      = None
        current_robot_state = "sleeping"
        previous_robot_state = "sleeping"
        wake_audio_time    = 0.0     # used to delay apertura until robot is ready

        try:
            while self.running:
                loop_start = time.time()
                frame = vision.read_frame()
                if frame is None:
                    continue

                # ── 1. Perception ──────────────────────────────────────
                t_p0 = time.time()
                vis = vision.estimate_attention(frame)
                t_p1 = time.time()
                mp_inf_ms = int((t_p1 - t_p0) * 1000)

                if time.time() - vlm_timer > 2.5:
                    self.vlm.analyze_frame(frame, current_robot_state, previous_robot_state)
                    vlm_timer = time.time()

                vlm = self.vlm.get_latest_result()

                # ── 2. Experimenter trigger ────────────────────────────
                if self.trigger_question:
                    sm.trigger_user_question()
                    self.trigger_question = False

                # ── 3. State machine update ────────────────────────────
                speech_status = {
                    "is_playing":     speech.is_playing,
                    "current_track":  speech.current_track,
                    "finished_track": (
                        speech.current_track
                        if speech.check_finished(speech.current_track)
                        else None
                    ),
                }

                t_sm0 = time.time()
                new_state, event_note = sm.update(vis, vlm, speech_status)
                t_sm1 = time.time()
                sm_update_ms = int((t_sm1 - t_sm0) * 1000)

                # ── 4. Robot pose ──────────────────────────────────────
                if new_state != current_robot_state:
                    robot.apply_state(new_state)
                    previous_robot_state = current_robot_state
                    current_robot_state = new_state

                # Expressive blink requested by state machine
                if sm.get_and_clear_blink():
                    robot.trigger_blink()

                # ── 5. Audio logic ─────────────────────────────────────
                audio_req = sm.get_and_clear_audio()
                if audio_req:
                    pending_audio = audio_req

                if pending_audio:
                    if pending_audio == "apertura":
                        # Wait until robot finishes moving AND 3s have passed
                        if not robot.is_interpolating():
                            if wake_audio_time == 0.0:
                                wake_audio_time = time.time()
                            if time.time() - wake_audio_time >= 3.0:
                                speech.play("apertura")
                                pending_audio  = None
                                wake_audio_time = 0.0
                    elif pending_audio in ("despedida", "desengagement"):
                        if not robot.is_interpolating():
                            speech.play(pending_audio)
                            pending_audio = None
                    elif pending_audio == "pausa":
                        speech.pause()
                        speech.play("pausa")   # plays over, pygame handles stop
                        pending_audio = None
                    elif pending_audio == "respuesta" and sm.main_response_paused:
                        # Resume from pause point
                        speech.resume()
                        pending_audio = None
                    else:
                        speech.play(pending_audio)
                        pending_audio = None

                robot.set_speaking(speech.is_busy())

                # ── 6. Logging ─────────────────────────────────────────
                motor_snap = robot.get_motor_snapshot()
                sm_metrics = sm.get_metrics()
                perf_metrics = {
                    "mediapipe_inference_ms": mp_inf_ms,
                    "sm_update_ms":          sm_update_ms
                }
                
                logger.log_event(
                    current_state   = new_state,
                    vision_results  = vis,
                    vlm_result      = vlm,
                    audio_state     = speech.get_audio_state(),
                    motor_snapshot  = motor_snap,
                    motor_cmd_count = robot.motor_command_count,
                    event_note      = event_note,
                    sm_metrics      = sm_metrics,
                    perf_metrics    = perf_metrics,
                    frame           = frame,
                )

                # ── 7. Push to UI ──────────────────────────────────────
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                with self._ui_lock:
                    self._ui_state.update({
                        "state":       new_state,
                        "face":        vis.get("face_detected", False),
                        "looking":     vis.get("is_looking", False),
                        "pitch":       vis.get("pitch", 0.0),
                        "yaw":         vis.get("yaw", 0.0),
                        "vlm":         vlm,
                        "audio_state": speech.get_audio_state(),
                        "frame_img":   img_rgb,
                    })

        except Exception as exc:
            print(f"[Main] Loop error: {exc}")
            import traceback; traceback.print_exc()
        finally:
            sm_metrics = sm.get_metrics()
            sm_metrics["motor_commands_count"] = robot.motor_command_count
            logger.save_summary(sm_metrics)
            robot.close()
            vision.close()
            speech.cleanup()
            self.stop_experiment()
            print("[Main] Experiment finished.")

    # ──────────────────────────── UI Refresh (main thread) ───────────────

    def _refresh_ui(self):
        with self._ui_lock:
            s = dict(self._ui_state)

        self._draw_dashboard(s)
        self._draw_video(s.get("frame_img"))
        self.status_bar.config(
            text=f"STATE: {s['state'].upper()}  |  "
                 f"Audio: {s['audio_state']}  |  "
                 f"Face: {'YES' if s['face'] else 'NO'}  "
                 f"Look: {'YES' if s['looking'] else 'NO'}"
        )

        self.root.after(50, self._refresh_ui)

    def _draw_dashboard(self, s: dict):
        c = self.dash
        c.delete("all")
        W = self.PANEL_W - 10
        y = 0

        def rect(x1, y1, x2, y2, fill, radius=6):
            c.create_rectangle(x1, y1, x2, y2, fill=fill, outline="", width=0)

        def text(x, yy, txt, font=FONT_LABEL, fill=TEXT_PRI, anchor="w"):
            c.create_text(x, yy, text=txt, font=font, fill=fill, anchor=anchor)

        def sep(yy):
            c.create_line(10, yy, W - 10, yy, fill=BORDER)
            return yy + 12

        # ── Header ────────────────────────────────────────────────────────
        rect(0, 0, W, 36, PANEL_BG)
        text(W // 2, 18, "ICCAS  Research  Dashboard",
             font=FONT_TITLE, fill=TEXT_PRI, anchor="center")
        y = 36

        # ── State badge ───────────────────────────────────────────────────
        state_name  = s.get("state", "sleeping")
        state_color = STATE_COLORS.get(state_name, "#444")
        rect(10, y + 8, W - 10, y + 42, state_color, radius=6)
        text(W // 2, y + 25, f"STATE:  {state_name.upper().replace('_', ' ')}",
             font=FONT_STATE, fill="white", anchor="center")
        y += 54

        y = sep(y)

        # ── MediaPipe section ─────────────────────────────────────────────
        text(12, y, "MediaPipe Perception", font=FONT_VALUE, fill=ACCENT)
        y += 18

        face_col    = "#66BB6A" if s["face"]    else "#EF5350"
        looking_col = "#66BB6A" if s["looking"] else "#EF5350"

        text(12,  y, "Face detected:", fill=TEXT_SEC)
        text(180, y, "YES" if s["face"]    else "NO",  fill=face_col)
        y += 16
        text(12,  y, "Is looking:", fill=TEXT_SEC)
        text(180, y, "YES" if s["looking"] else "NO",  fill=looking_col)
        y += 16
        text(12,  y, "Pitch:", fill=TEXT_SEC)
        text(180, y, f"{s['pitch']:+.1f}°",  fill=TEXT_PRI)
        y += 16
        text(12,  y, "Yaw:", fill=TEXT_SEC)
        text(180, y, f"{s['yaw']:+.1f}°",   fill=TEXT_PRI)
        y += 10

        y = sep(y)

        # ── VLM section ───────────────────────────────────────────────────
        vlm = s.get("vlm", {})
        text(12, y, "VLM Situational Awareness", font=FONT_VALUE, fill=ACCENT)
        y += 18

        avail     = vlm.get("interaction_availability", "—")
        avail_col = {"high": "#66BB6A", "medium": "#FFD54F", "low": "#EF5350"}.get(avail, TEXT_SEC)

        text(12,  y, "Robot state:", fill=TEXT_SEC)
        text(180, y, str(vlm.get("robot_state", "—")).upper(), fill=TEXT_PRI)
        y += 16
        text(12,  y, "Attention target:", fill=TEXT_SEC)
        text(180, y, str(vlm.get("attention_target", "—")), fill=TEXT_PRI)
        y += 16
        text(12,  y, "Availability:", fill=TEXT_SEC)
        text(180, y, avail.upper(), fill=avail_col)
        y += 16
        text(12,  y, "Confidence:", fill=TEXT_SEC)
        text(180, y, str(vlm.get("confidence", "—")), fill=TEXT_PRI)
        y += 18

        summary = vlm.get("scene_summary", "")
        if summary:
            # Word-wrap summary into 2 lines max
            words  = summary.split()
            line1, line2 = [], []
            for w in words:
                if len(" ".join(line1 + [w])) < 46:
                    line1.append(w)
                elif len(" ".join(line2 + [w])) < 46:
                    line2.append(w)
            text(12, y, " ".join(line1), fill=TEXT_SEC, font=FONT_MONO)
            y += 13
            if line2:
                text(12, y, " ".join(line2), fill=TEXT_SEC, font=FONT_MONO)
                y += 13

        y = sep(y + 4)

        # ── Audio section ─────────────────────────────────────────────────
        audio_state = s.get("audio_state", "idle")
        text(12, y, "Audio", font=FONT_VALUE, fill=ACCENT)
        y += 18

        if audio_state.startswith("playing"):
            a_col  = "#66BB6A"
            a_text = f"▶  {audio_state.split(':')[-1].upper()}"
        elif audio_state.startswith("paused"):
            a_col  = "#FFD54F"
            a_text = f"⏸  {audio_state.split(':')[-1].upper()}"
        else:
            a_col  = TEXT_SEC
            a_text = "●  IDLE"

        rect(10, y, W - 10, y + 24, "#1A1E2A")
        text(20, y + 12, a_text, font=FONT_VALUE, fill=a_col)
        y += 32

        y = sep(y)

    def _draw_video(self, img_rgb):
        if img_rgb is None:
            return
        try:
            pil_img = PIL.Image.fromarray(img_rgb).resize(
                (self.VIDEO_W, self.VIDEO_H), PIL.Image.NEAREST
            )
            tk_img = PIL.ImageTk.PhotoImage(image=pil_img)
            self.video_canvas.create_image(0, 0, anchor="nw", image=tk_img)
            self.video_canvas._img_ref = tk_img   # prevent GC
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = ICCAS_Dashboard(root)
    root.mainloop()
