import os
import uuid
import tempfile
from django.db import models
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from PIL import Image
import numpy as np
import cv2

User = get_user_model()

def snapshot_upload_to(instance, filename):
    """
    Chemin dynamique de sauvegarde pour les snapshots.
    Exemple : snapshots/2025/06/04/<uuid4>.jpg
    """
    now = timezone.now()
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    # Utiliser un UUID pour éviter les collisions de noms
    new_name = f"{uuid.uuid4().hex}{ext}"
    return os.path.join(
        "snapshots",
        str(now.year),
        str(now.month).zfill(2),
        str(now.day).zfill(2),
        new_name
    )

def clip_upload_to(instance, filename):
    """
    Chemin de sauvegarde pour les petits extraits vidéo (clips).
    Exemple : clips/2025/06/04/<uuid4>.mp4
    """
    now = timezone.now()
    ext = os.path.splitext(filename)[1].lower() or ".mp4"
    new_name = f"{uuid.uuid4().hex}{ext}"
    return os.path.join(
        "clips",
        str(now.year),
        str(now.month).zfill(2),
        str(now.day).zfill(2),
        new_name
    )

class FallAlert(models.Model):
    """
    Représente un incident de chute détecté.
    - timestamp : date et heure de la détection
    - detected_by : source (live_camera, upload_test, etc.)
    - image_snapshot : photo du moment de la détection
    - video_clip : (optionnel) extrait vidéo autour de la détection
    - description : notes libre
    - yolo_confidence : confiance retournée par YOLO
    - yolo_class : classe identifiée par YOLO (ex : 'fall', 'person', etc.)
    - metadata : JSON brut retourné par le modèle (boxes, keypoints, etc.)
    - acknowledged, acknowledged_by, acknowledged_at : flux de validation par un employé
    - is_accurate : whether the detection was accurate (True/False/None)
    - accuracy_marked_by : user who marked the accuracy
    - accuracy_marked_at : when accuracy was marked
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    detected_by = models.CharField(
        max_length=64,
        default="webcam",
        help_text="Source of detection (e.g. 'live_camera', 'upload_test')."
    )
    image_snapshot = models.ImageField(
        upload_to=snapshot_upload_to,
        blank=True,
        null=True,
        help_text="Optional snapshot of the frame where the fall was detected."
    )
    video_clip = models.FileField(
        upload_to=clip_upload_to,
        blank=True,
        null=True,
        help_text="Optional short video clip around the fall detection."
    )
    description = models.TextField(
        blank=True,
        help_text="Any additional notes about this detection."
    )
    yolo_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence score from YOLO model at detection time."
    )
    yolo_class = models.CharField(
        max_length=64,
        blank=True,
        help_text="Class name predicted by YOLO (e.g. 'fall', 'person')."
    )
    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Raw JSON output from YOLO (boxes, scores, keypoints, etc.)."
    )
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether an employee has marked this as reviewed."
    )
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts"
    )
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True
    )
    is_accurate = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether this detection was accurate (True=accurate, False=false positive, None=not marked)"
    )
    accuracy_marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accuracy_marked_alerts"
    )
    accuracy_marked_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        status = "ACK" if self.acknowledged else "NEW"
        return f"FallAlert [{status}] at {self.timestamp:%Y-%m-%d %H:%M:%S}"

    def save_snapshot_from_frame(self, frame: np.ndarray):
        """
        Prend une frame OpenCV (BGR numpy.ndarray), la convertit en JPEG
        et l'enregistre dans image_snapshot. Appelle save() à la fin.
        """
        # Convertir BGR → RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Utiliser PIL pour encoder en JPEG
        img_pil = Image.fromarray(rgb)
        tmp_io = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img_pil.save(tmp_io, format="JPEG")
        tmp_io.flush()
        tmp_io.seek(0)

        # Générer un nom de fichier unique
        filename = os.path.basename(tmp_io.name)
        django_file = ContentFile(tmp_io.read(), name=filename)
        self.image_snapshot.save(filename, django_file, save=False)

        tmp_io.close()
        try:
            os.unlink(tmp_io.name)
        except OSError:
            pass

    def mark_acknowledged(self, user):
        """
        Marque l'alerte comme validée par un employé.
        """
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()

    def mark_accuracy(self, user, is_accurate):
        """
        Mark the accuracy of this alert.
        """
        self.is_accurate = is_accurate
        self.accuracy_marked_by = user
        self.accuracy_marked_at = timezone.now()
        self.save()