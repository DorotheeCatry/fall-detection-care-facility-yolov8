"""
Models for the detection app.

Defines the FallAlert model, which represents a detected fall incident,
and utility functions for dynamically generating upload paths for snapshots and video clips.
"""

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
    Generate a dynamic upload path for snapshot images.

    The path format is: snapshots/YYYY/MM/DD/<uuid4>.jpg

    Args:
        instance: The model instance (FallAlert).
        filename: The original filename.

    Returns:
        str: The upload path for the snapshot.
    """
    now = timezone.now()
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    # Use a UUID to avoid filename collisions
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
    Generate a dynamic upload path for video clips.

    The path format is: clips/YYYY/MM/DD/<uuid4>.mp4

    Args:
        instance: The model instance (FallAlert).
        filename: The original filename.

    Returns:
        str: The upload path for the video clip.
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
    Represents a detected fall incident.

    Fields:
        timestamp: Date and time of detection.
        detected_by: Source of detection (e.g., 'live_camera', 'upload_test').
        image_snapshot: Optional snapshot image of the detection moment.
        video_clip: Optional short video clip around the detection.
        description: Free-form notes about the detection.
        yolo_confidence: Confidence score from YOLO model.
        yolo_class: Class name predicted by YOLO (e.g., 'fall', 'person').
        metadata: Raw JSON output from YOLO (boxes, scores, keypoints, etc.).
        acknowledged: Whether an employee has marked this as reviewed.
        acknowledged_by: User who acknowledged the alert.
        acknowledged_at: Timestamp when the alert was acknowledged.
        is_accurate: Whether the detection was accurate (True/False/None).
        accuracy_marked_by: User who marked the accuracy.
        accuracy_marked_at: Timestamp when accuracy was marked.
        fall_state: Fall state (monitoring, alert, urgent, recovered).
        time_on_ground: Time spent on ground in seconds.
    """
    
    FALL_STATE_CHOICES = [
        ('monitoring', 'Monitoring'),
        ('alert', 'Alert'),
        ('urgent', 'Urgent'),
        ('recovered', 'Recovered'),
    ]
    
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
    fall_state = models.CharField(
        max_length=20,
        choices=FALL_STATE_CHOICES,
        blank=True,
        help_text="Fall state (monitoring, alert, urgent, recovered)"
    )
    time_on_ground = models.FloatField(
        null=True,
        blank=True,
        help_text="Time spent on ground in seconds"
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        """
        Return a human-readable string representation of the FallAlert instance,
        indicating its status (ACK or NEW) and the timestamp of detection.
        """
        status = "ACK" if self.acknowledged else "NEW"
        state_info = f" [{self.fall_state.upper()}]" if self.fall_state else ""
        return f"FallAlert [{status}]{state_info} at {self.timestamp:%Y-%m-%d %H:%M:%S}"

    def save_snapshot_from_frame(self, frame: np.ndarray):
        """
        Save an OpenCV frame (BGR numpy.ndarray) as a JPEG image to image_snapshot.

        Converts the frame from BGR to RGB, encodes it as JPEG using PIL,
        and saves it to the image_snapshot field. Cleans up the temporary file after saving.
        """
        # Convert BGR to RGB for PIL compatibility
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(rgb)
        tmp_io = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img_pil.save(tmp_io, format="JPEG")
        tmp_io.flush()
        tmp_io.seek(0)

        # Generate a unique filename and save to the model field
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
        Mark this alert as acknowledged by the given user.

        Sets acknowledged to True, records the user and the current timestamp,
        and saves the model instance.
        """
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()

    def mark_accuracy(self, user, is_accurate):
        """
        Mark the accuracy of this alert.

        Args:
            user: The user marking the accuracy.
            is_accurate (bool): True if the detection was accurate, False otherwise.

        Updates the is_accurate field, records the user and timestamp, and saves the model.
        """
        self.is_accurate = is_accurate
        self.accuracy_marked_by = user
        self.accuracy_marked_at = timezone.now()
        self.save()
        
    def get_urgency_color(self):
        """Returns CSS color corresponding to fall state."""
        color_map = {
            'monitoring': 'yellow',
            'alert': 'orange', 
            'urgent': 'red',
            'recovered': 'green'
        }
        return color_map.get(self.fall_state, 'gray')
    
    def get_urgency_display(self):
        """Returns display text for fall state."""
        display_map = {
            'monitoring': 'Monitoring',
            'alert': 'Alert',
            'urgent': 'Urgent',
            'recovered': 'Recovered'
        }
        return display_map.get(self.fall_state, 'Unknown')