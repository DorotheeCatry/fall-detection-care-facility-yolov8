from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class FallAlert(models.Model):
    """
    Represents one detected fall incident.
    We'll add more fields later (e.g. snapshot image, video path, YOLO metadata).
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    detected_by = models.CharField(
        max_length=64,
        default="webcam",
        help_text="Source of detection (e.g. 'live_camera', 'upload_test')."
    )
    image_snapshot = models.ImageField(
        upload_to="snapshots/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Optional snapshot of the frame where the fall was detected."
    )
    description = models.TextField(
        blank=True,
        help_text="Any additional notes about this detection."
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

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"FallAlert at {self.timestamp} (ack={self.acknowledged})"
