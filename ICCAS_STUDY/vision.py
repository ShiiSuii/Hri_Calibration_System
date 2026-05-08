import cv2
import mediapipe as mp
import numpy as np
from config import THRESHOLDS

class VisionPerception:
    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)
        
        # Initialize MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # 3D model points for head pose estimation
        self.model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left Mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ])
        
    def estimate_attention(self, frame):
        # Default outputs
        results_out = {
            "face_detected": False,
            "is_looking": False,
            "pitch": 0.0,
            "yaw": 0.0,
            "roll": 0.0,
            "face_center": (0.5, 0.5), # Normalized x, y
            "frame": frame
        }
        
        if frame is None:
            return results_out
            
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        if results.multi_face_landmarks:
            results_out["face_detected"] = True
            
            for face_landmarks in results.multi_face_landmarks:
                img_h, img_w, img_c = frame.shape
                
                # 2D image points from MediaPipe landmarks
                face_2d = []
                idx_to_coor = {}
                for idx, lm in enumerate(face_landmarks.landmark):
                    if idx in [1, 152, 33, 263, 61, 291]:
                        x, y = int(lm.x * img_w), int(lm.y * img_h)
                        face_2d.append([x, y])
                        idx_to_coor[idx] = (x, y)
                
                # Reorder to match model_points
                image_points = np.array([
                    idx_to_coor[1],
                    idx_to_coor[152],
                    idx_to_coor[33],
                    idx_to_coor[263],
                    idx_to_coor[61],
                    idx_to_coor[291]
                ], dtype="double")
                
                # Camera internals
                focal_length = img_w
                center = (img_w / 2, img_h / 2)
                camera_matrix = np.array([
                    [focal_length, 0, center[0]],
                    [0, focal_length, center[1]],
                    [0, 0, 1]
                ], dtype="double")
                
                dist_coeffs = np.zeros((4, 1)) # Assuming no lens distortion
                
                # Solve PnP
                success, rotation_vector, translation_vector = cv2.solvePnP(
                    self.model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
                )
                
                if success:
                    # Get rotational matrix
                    rmat, jac = cv2.Rodrigues(rotation_vector)
                    # Get angles
                    angles, mtxR, mtxQ, Qx, Qy, Qz = cv2.RQDecomp3x3(rmat)
                    
                    pitch = angles[0]
                    yaw = angles[1]
                    roll = angles[2]
                    
                    # Normalize pitch/yaw
                    if pitch > 90: pitch -= 180
                    elif pitch < -90: pitch += 180
                    if yaw > 90: yaw -= 180
                    elif yaw < -90: yaw += 180
                    
                    results_out["pitch"] = pitch
                    results_out["yaw"] = yaw
                    results_out["roll"] = roll
                    
                    # Calculate Face Center
                    results_out["face_center"] = (face_landmarks.landmark[1].x, face_landmarks.landmark[1].y)
                    
                    # Attention Heuristic from Config
                    p_lim = THRESHOLDS["attention_pitch_limit"]
                    y_lim = THRESHOLDS["attention_yaw_limit"]
                    
                    if -p_lim < pitch < p_lim and -y_lim < yaw < y_lim:
                        results_out["is_looking"] = True
                        color = (0, 200, 0) # Green
                    else:
                        results_out["is_looking"] = False
                        color = (0, 0, 255) # Red

                    # Visualization logic
                    (nose_end_point2D, _) = cv2.projectPoints(np.array([(0.0, 0.0, 500.0)]), rotation_vector, translation_vector, camera_matrix, dist_coeffs)
                    p1 = (int(image_points[0][0]), int(image_points[0][1]))
                    p2 = (int(nose_end_point2D[0][0][0]), int(nose_end_point2D[0][0][1]))
                    cv2.line(frame, p1, p2, color, 3)
                    
                    mp.solutions.drawing_utils.draw_landmarks(
                        image=frame,
                        landmark_list=face_landmarks,
                        connections=self.mp_face_mesh.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp.solutions.drawing_styles.get_default_face_mesh_contours_style()
                    )
                    
                    def draw_text(img, text, pos, col):
                        cv2.putText(img, text, (pos[0]+1, pos[1]+1), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
                        cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

                    draw_text(frame, f"ATTENTION: {'YES' if results_out['is_looking'] else 'NO'}", (20, 40), color)
                    draw_text(frame, f"Pitch: {pitch:.1f}", (20, 75), (0,0,0))
                    draw_text(frame, f"Yaw: {yaw:.1f}", (20, 105), (0,0,0))
                    
        return results_out

    def read_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        return cv2.flip(frame, 1)

    def close(self):
        self.cap.release()
        cv2.destroyAllWindows()
