import threading
import time
import json
import queue
import base64
import requests
import cv2
import numpy as np

class VLMWorker:
    """
    Background worker that classifies the scene using Ollama (VLM).
    
    Provides situational awareness from the robot's egocentric perspective,
    contextualized by the robot's internal state.
    """

    def __init__(self, model_id="moondream", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host
        self.running = True
        self._input_q = queue.Queue(maxsize=1)
        
        # Default result structure
        self._last_res = {
            "robot_state": "unknown",
            "person_present": False,
            "attention_target": "unknown",
            "interaction_availability": "low",
            "visible_objects": [],
            "scene_summary": "VLM starting up...",
            "confidence": "low"
        }

        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def _worker_loop(self):
        print(f"[VLM] Ollama Worker started using model: {self.model_id}")
        
        while self.running:
            try:
                # Wait for a request (frame + states)
                task = self._input_q.get(timeout=1.0)
                frame, current_state, previous_state = task
                
                t0 = time.time()
                
                # Convert frame to base64 for Ollama
                _, buffer = cv2.imencode('.jpg', frame)
                img_base64 = base64.b64encode(buffer).decode('utf-8')

                prompt = (
                    "You are analyzing an egocentric visual scene from the head of an expressive humanoid robot. "
                    "The camera is mounted above the robot’s skull, so the image represents the robot’s own visual perspective. "
                    "The robot may slightly move its head, which changes the camera view. "
                    f"The robot is currently in the following internal interaction state: {current_state.upper()}. "
                    f"Optionally, the previous state was: {previous_state.upper()}. "
                    "Your task is to describe the current social situation around the robot in a short and structured way, "
                    "taking into account both the visual scene and the current interaction state of the robot. "
                    "Focus on whether a person is present, whether that person appears visually engaged with the robot, "
                    "whether the person is looking at a phone or elsewhere, whether the interaction seems available or unavailable, "
                    "and which relevant objects are visible. Do not generate long explanations. "
                    "Output only the predefined structured format."
                    "\n\nOutput ONLY a valid JSON object with the following keys:\n"
                    "{\n"
                    f'  "robot_state": "{current_state}",\n'
                    '  "person_present": true/false,\n'
                    '  "attention_target": "robot/phone/elsewhere/none/unknown",\n'
                    '  "interaction_availability": "high/medium/low",\n'
                    '  "visible_objects": ["phone", "table", "chair"],\n'
                    '  "scene_summary": "Breve descripción situada desde la perspectiva del robot y consistente con su estado actual.",\n'
                    '  "confidence": "low/medium/high"\n'
                    "}"
                )

                # Call Ollama API
                payload = {
                    "model": self.model_id,
                    "prompt": prompt,
                    "images": [img_base64],
                    "stream": False,
                    "format": "json"
                }

                try:
                    response = requests.post(f"{self.host}/api/generate", json=payload, timeout=15)
                    inf_time = time.time() - t0
                    if response.status_code == 200:
                        raw_response = response.json().get("response", "{}")
                        parsed = json.loads(raw_response)
                        
                        # Ensure robot_state is consistent
                        parsed["robot_state"] = current_state
                        parsed["inference_time_ms"] = int(inf_time * 1000)
                        
                        # Fallback for missing keys
                        for k, v in self._last_res.items():
                            if k not in parsed:
                                parsed[k] = v
                                
                        self._last_res = parsed
                        print(f"[VLM] Inferred: {parsed.get('attention_target')} | Conf: {parsed.get('confidence')} ({inf_time:.2f}s)")
                    else:
                        print(f"[VLM] Ollama error: {response.status_code}")
                except Exception as e:
                    print(f"[VLM] Request failed: {e}")
                    self._last_res["scene_summary"] = "Connection to Ollama failed."

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[VLM] Worker error: {e}")

    def analyze_frame(self, frame, current_state="unknown", previous_state="unknown"):
        """Submit a frame and robot context for analysis."""
        try:
            # We use put_nowait to avoid blocking the main loop; if the queue is full, we skip the frame.
            self._input_q.put_nowait((frame, current_state, previous_state))
        except queue.Full:
            pass

    def get_latest_result(self) -> dict:
        """Return the most recent VLM result dict."""
        return dict(self._last_res)

    def stop(self):
        self.running = False
