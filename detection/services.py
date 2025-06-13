# detection/services.py

from ultralytics import YOLO
import cv2
import os
import uuid
import tempfile
from django.core.files.base import ContentFile
from .models import FallAlert
import numpy as np
from typing import Tuple, List
from ultralytics.engine.results import Results


class FallDetectionService:
    def __init__(self, 
                 model_path: str = '/home/utilisateur/Documents/Brief_Computer_Vision/fall-detection-care-facility-yolov8/model_dl/best.pt',
                 conf_threshold: float = 0.7
                ) -> None:
        """
        conf_threshold: minimal confidence (0–1) to count as a fall.
        """
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold

    def run_model(self, image: np.ndarray) -> List[Results]:
        """
        Run raw YOLO inference on the BGR image and return the list of Results.
        """
        return self.model(image)

    def detect_falls(self, image: np.ndarray) -> Tuple[bool, float | None]:
        """
        Reçoit une image NumPy (BGR) et renvoie (True, confidence)
        si la classe 'Fall-Detected' est trouvée avec conf >= conf_threshold,
        sinon (False, None).
        """
        results = self.run_model(image)
        for r in results:
            for box in r.boxes:
                cls_id   = int(box.cls)
                cls_name = r.names.get(cls_id, "")
                conf     = float(box.conf)
                if cls_name == "Fall-Detected" and conf >= self.conf_threshold:
                    return True, conf
        return False, None


class VideoClipService:
    """
    Service utilitaire pour générer un petit clip autour du timestamp de détection.
    On suppose que la caméra envoie du RTSP/UDP que l’on lit en continu,
    et qu’on connaît approximativement l’instant de la chute.
    """
    def __init__(self, source_url):
        self.source_url = source_url  # ex: "rtsp://192.168.1.100:554/stream"

    def extract_clip(self, start_time: float, duration: float = 10.0) -> (str, bytes):
        """
        Extrait un clip de `duration` secondes à partir de `start_time` (timestamp UNIX).
        Retourne (filename, binary_data) pour l’enregistrer.
        """
        cap = cv2.VideoCapture(self.source_url)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        # Créer un fichier temporaire pour le clip
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        filename = os.path.basename(temp_file.name)
        out = None

        # Calculer l’index de la frame de départ
        cap.set(cv2.CAP_PROP_POS_MSEC, (start_time - duration/2) * 1000)

        frames_to_write = int(duration * fps)
        written = 0

        while written < frames_to_write:
            ret, frame = cap.read()
            if not ret:
                break
            if out is None:
                height, width, _ = frame.shape
                out = cv2.VideoWriter(temp_file.name, fourcc, fps, (width, height))
            out.write(frame)
            written += 1

        cap.release()
        if out:
            out.release()

        with open(temp_file.name, "rb") as f:
            data = f.read()

        try:
            os.unlink(temp_file.name)
        except OSError:
            pass

        return filename, data

    def attach_clip_to_alert(self, alert: FallAlert, start_time: float, duration: float = 10.0):
        """
        Extrait un clip autour de `start_time` et le sauvegarde dans `alert.video_clip`.
        """
        filename, data = self.extract_clip(start_time, duration)
        alert.video_clip.save(filename, ContentFile(data), save=True)

