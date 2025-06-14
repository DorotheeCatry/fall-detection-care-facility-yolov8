"""
Services for the detection app.

This module provides service classes for fall detection using YOLO models
and for generating and attaching video clips to alerts. It includes:
- FallDetectionService: Runs YOLO inference and determines if a fall is detected.
- VideoClipService: Extracts short video clips from a camera stream and attaches them to FallAlert instances.
"""

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
    """
    Service for running YOLO-based fall detection on images.

    Attributes:
        model_path (str): Path to the YOLO model weights.
        conf_threshold (float): Minimum confidence to count as a fall.
    """
    def __init__(
        self, 
        model_path: str = 'model_dl/best.pt',
        conf_threshold: float = 0.7
    ) -> None:
        """
        Initialize the YOLO model and set the confidence threshold.

        Args:
            model_path (str): Path to the YOLO model weights.
            conf_threshold (float): Minimum confidence to count as a fall.
        """
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold

    def run_model(self, image: np.ndarray) -> List[Results]:
        """
        Run raw YOLO inference on the BGR image and return the list of Results.

        Args:
            image (np.ndarray): Input image in BGR format.

        Returns:
            List[Results]: YOLO inference results.
        """
        return self.model(image)

    def detect_falls(self, image: np.ndarray) -> Tuple[bool, float | None]:
        """
        Analyze an image and determine if a fall is detected.

        Args:
            image (np.ndarray): Input image in BGR format.

        Returns:
            Tuple[bool, float | None]: (True, confidence) if a fall is detected with
            confidence >= threshold, otherwise (False, None).
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
    Utility service for generating a short video clip around the detection timestamp.

    Assumes the camera provides an RTSP/UDP stream and that the approximate
    fall instant is known.
    """
    def __init__(self, source_url):
        """
        Initialize the video clip service.

        Args:
            source_url (str): RTSP/UDP stream URL of the camera.
        """
        self.source_url = source_url  # ex: "rtsp://192.168.1.100:554/stream"

    def extract_clip(self, start_time: float, duration: float = 10.0) -> (str, bytes):
        """
        Extract a video clip of `duration` seconds starting from `start_time` (UNIX timestamp).

        Args:
            start_time (float): Start time in UNIX timestamp.
            duration (float): Duration of the clip in seconds.

        Returns:
            tuple: (filename, binary_data) for saving.
        """
        cap = cv2.VideoCapture(self.source_url)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        # Create a temporary file for the clip
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        filename = os.path.basename(temp_file.name)
        out = None

        # Set the starting position in the video stream
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
        Attach a generated video clip to a FallAlert instance.

        Args:
            alert (FallAlert): The alert instance to attach the clip to.
            start_time (float): Start time in UNIX timestamp.
            duration (float): Duration of the clip in seconds.

        Note:
            The commented code below is an alternative implementation for extracting
            and saving a video clip. It is kept for reference and may be useful for
            debugging or future improvements.
        """
        # --- Alternative implementation (kept for reference) ---
        """
        cap = cv2.VideoCapture(self.source_url)
        if not cap.isOpened():
            raise RuntimeError("Impossible d'ouvrir le flux vidéo")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25.0  # default value

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        filename = os.path.basename(temp_file.name)

        # Read the first frame to get the size
        ret, frame = cap.read()
        if not ret:
            cap.release()
            temp_file.close()
            raise RuntimeError("Impossible de lire une frame du flux")

        height, width = frame.shape[:2]
        out = cv2.VideoWriter(temp_file.name, fourcc, fps, (width, height))

        # Write the first frame
        out.write(frame)

        # Calculate number of frames to write
        frames_to_write = int(duration * fps) - 1  # one frame already written
        for _ in range(frames_to_write):
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)

        cap.release()
        out.release()

        with open(temp_file.name, "rb") as f:
            data = f.read()

        try:
            os.unlink(temp_file.name)
        except OSError:
            pass

        alert.video_clip.save(filename, ContentFile(data), save=True)
        """
        pass  # The actual implementation is provided in extract_clip()

