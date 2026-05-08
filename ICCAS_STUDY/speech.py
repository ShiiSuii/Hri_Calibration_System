import pygame
from gtts import gTTS
import tempfile
import os
import time


class SpeechEngine:
    """
    Generates and plays scripted audio using gTTS + pygame.

    All audio files are pre-generated at experiment start to avoid
    latency during the session.
    """

    SCRIPT = {
        "apertura":     "Hola. Estoy listo para conversar.",
        "disponibilidad": "Te escucho.",
        "respuesta": (
            "La inteligencia artificial es una rama de la informática que busca crear sistemas "
            "capaces de realizar tareas que normalmente requieren inteligencia humana, "
            "como reconocer imágenes, comprender lenguaje o tomar decisiones. "
            "En otras palabras, permite que una máquina procese información y actúe de forma útil "
            "según lo que percibe."
        ),
        "pausa":        "Te espero. Cuando termines, continúo.",
        "reanudacion":  "Continúo.",
        "cierre":       "Eso es, de forma breve, la inteligencia artificial.",
        "despedida":    "Hasta luego.",
        "desengagement": "Vuelvo a descansar. Cuando quieras, podemos continuar.",
    }

    def __init__(self):
        pygame.mixer.init()
        self.is_playing  = False
        self.is_paused   = False
        self.current_track: str | None = None
        self.temp_files: dict[str, str] = {}

    # ─────────────────────────── Setup ───────────────────────────────────

    def generate_all(self):
        """Pre-generate all script audio files. Call once before experiment starts."""
        print("[Speech] Generating audio files with gTTS...")
        for key, text in self.SCRIPT.items():
            tts = gTTS(text=text, lang="es")
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            fp.close()
            tts.save(fp.name)
            self.temp_files[key] = fp.name
        print("[Speech] All audio files ready.")

    # ─────────────────────────── Playback ────────────────────────────────

    def play(self, track_key: str):
        if track_key not in self.temp_files:
            print(f"[Speech] Track '{track_key}' not found.")
            return

        # If same track is paused, resume instead
        if self.is_paused and self.current_track == track_key:
            self.resume()
            return

        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        pygame.mixer.music.load(self.temp_files[track_key])
        pygame.mixer.music.play()
        self.current_track = track_key
        self.is_playing    = True
        self.is_paused     = False
        print(f"[Speech] Playing: {track_key}")

    def pause(self):
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused  = True
            self.is_playing = False
            print("[Speech] Paused.")

    def resume(self):
        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused  = False
            self.is_playing = True
            print("[Speech] Resumed.")

    def stop(self):
        pygame.mixer.music.stop()
        self.is_playing    = False
        self.is_paused     = False
        self.current_track = None

    # ─────────────────────────── Status ──────────────────────────────────

    def is_busy(self) -> bool:
        """True if audio is actively playing (not paused)."""
        return pygame.mixer.music.get_busy()

    def check_finished(self, track_key: str) -> bool:
        """
        Returns True once when the specified track finishes playing naturally.
        Resets is_playing flag on detection.
        """
        if (
            self.current_track == track_key
            and not pygame.mixer.music.get_busy()
            and not self.is_paused
            and self.is_playing
        ):
            self.is_playing = False
            return True
        return False

    def get_position_ms(self) -> int:
        """Current playback position in milliseconds (0 if not playing)."""
        return max(0, pygame.mixer.music.get_pos())

    def get_audio_state(self) -> str:
        """Returns a loggable string: 'playing:<track>', 'paused:<track>', or 'idle'."""
        if self.is_paused and self.current_track:
            return f"paused:{self.current_track}"
        if self.is_busy() and self.current_track:
            return f"playing:{self.current_track}"
        return "idle"

    # ─────────────────────────── Cleanup ─────────────────────────────────

    def cleanup(self):
        self.stop()
        for path in self.temp_files.values():
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        self.temp_files = {}
        print("[Speech] Temp files cleaned up.")
