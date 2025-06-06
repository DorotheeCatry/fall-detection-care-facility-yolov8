# detection/services.py
from ultralytics import YOLO
import cv2
import os
import uuid
import tempfile
from django.core.files.base import ContentFile
from .models import FallAlert

from ultralytics import YOLO
import cv2
import numpy as np

class FallDetectionService:
    def __init__(self):
        # Remplacez le chemin ci-dessous par la localisation de votre .pt
        self.model = YOLO('/home/utilisateur/Documents/Brief_Computer_Vision/fall-detection-care-facility-yolov8/model_dl/best.pt')

    def detect_falls(self, image: np.ndarray) -> bool:
        """
        Reçoit une image NumPy (BGR) et renvoie True si la classe 'fall'
        est détectée avec une confiance > 0.5 (par ex.), sinon False.
        """
        results = self.model(image)  # inference YOLO sur l’image
        for r in results:  # r correspond à un objet Results
            # r.boxes contient la liste des objets détectés dans l’image
            for box in r.boxes:
                cls_id = int(box.cls)
                cls_name = r.names.get(cls_id, "")
                print("Detected class:", cls_name)
                conf = float(box.conf)
                # Suppose que votre modèle a bien une classe nommée "fall"
                if cls_name == "Fall-Detected" and conf > 0.8:
                    return True
        return False


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

