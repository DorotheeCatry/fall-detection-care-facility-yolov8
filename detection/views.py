# detection/views.py

import os
import cv2
import numpy as np
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, FormView, TemplateView, RedirectView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponseBadRequest
import base64

from .models import FallAlert
from .forms import TestDetectionForm
from .services import FallDetectionService, VideoClipService

import json
import json
import base64
import cv2
import numpy as np
from django.views import View
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin


# Instanciation globale du service pour éviter de recharger le modèle à chaque requête
fall_service = FallDetectionService()

class AlertListView(LoginRequiredMixin, ListView):
    model = FallAlert
    template_name = "detection/alerts_list.html"
    context_object_name = "alerts"
    paginate_by = 20


class AcknowledgeAlertView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        alert = get_object_or_404(FallAlert, pk=kwargs["pk"])
        alert.acknowledged = True
        alert.acknowledged_by = self.request.user
        alert.acknowledged_at = timezone.now()
        alert.save()
        messages.success(self.request, "Alert acknowledged successfully.")
        return reverse_lazy("detection:alerts")


class TestDetectionView(LoginRequiredMixin, FormView):
    template_name = "detection/test_detection.html"
    form_class = TestDetectionForm
    success_url = reverse_lazy("detection:test_detection")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_camera_enabled"] = True
        return context

    def form_valid(self, form):
        upload = form.cleaned_data["upload_file"]
        description = form.cleaned_data.get("description", "")

        # 1. Sauvegarder temporairement le fichier pour que OpenCV puisse le lire
        temp_path = None
        try:
            if hasattr(upload, "temporary_file_path"):
                temp_path = upload.temporary_file_path()
            else:
                import tempfile
                suffix = os.path.splitext(upload.name)[1]  # ex: ".mp4" ou ".jpg"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in upload.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()
                temp_path = tmp.name

            # 2. Détecter s’il s’agit d’une image ou d’une vidéo, et récupérer la première frame
            ext = os.path.splitext(upload.name)[1].lower()
            if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
                frame = cv2.imdecode(
                    np.fromfile(temp_path, dtype=np.uint8),
                    cv2.IMREAD_COLOR
                )
            else:
                cap = cv2.VideoCapture(temp_path)
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    raise ValueError("Impossible de lire la première frame de la vidéo.")

            # 3. Appel au modèle YOLOv8 via le service
            results = fall_service.detect_falls(frame)

            # 4. Interpréter `results` pour savoir s'il y a eu chute
            fall_detected = False
            for r in results:  
                for box in r.boxes:
                    if int(box.cls) == 0 and float(box.conf) > 0.5:
                        fall_detected = True
                        break
                if fall_detected:
                    break

            # 5. On crée l’alerte si nécessaire
            if fall_detected:
                FallAlert.objects.create(
                    detected_by="test_upload",
                    description=(description or f"Test upload: {upload.name}"),
                )
                messages.success(self.request, "Fall detected ! Alerte créée.")
            else:
                messages.info(self.request, "Aucune chute détectée pour ce fichier.")

        except Exception as e:
            messages.error(self.request, f"Error processing upload: {str(e)}")

        finally:
            if temp_path and not hasattr(upload, "temporary_file_path"):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        return super().form_valid(form)


class LiveDetectionView(LoginRequiredMixin, TemplateView):
    template_name = "detection/live_detection.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_camera_enabled"] = True
        return context


class CreateAlertView(LoginRequiredMixin, View):
    """
    CBV qui crée un FallAlert à partir d'un POST JSON JavaScript (live detection).
    On gère les champs yolo_confidence, yolo_class, metadata, snapshot, et clip vidéo.
    """

    def post(self, request, *args, **kwargs):
        # 1. Charger le JSON du body
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")

        # 2. Extraire ce qu'on attend :
        alert_type     = payload.get("type", "live_camera")
        description    = payload.get("description", "")
        yolo_conf      = payload.get("yolo_confidence")
        yolo_cls       = payload.get("yolo_class")
        metadata_json  = payload.get("metadata")
        snapshot_b64   = payload.get("snapshot_b64")
        create_clip    = payload.get("make_clip")

        # 3. Créer un objet sans le sauvegarder immédiatement
        new_alert = FallAlert(
            detected_by     = alert_type,
            description     = description,
            yolo_confidence = yolo_conf,
            yolo_class      = yolo_cls or "",
            metadata        = metadata_json
        )

        # 4. Si le client JS envoie un snapshot en base64, on l’assigne :
        if snapshot_b64:
            import base64, uuid
            from django.core.files.base import ContentFile

            header, data = snapshot_b64.split(",", 1)
            try:
                decoded = base64.b64decode(data)
            except (ValueError, TypeError):
                decoded = None

            if decoded:
                filename = f"{uuid.uuid4().hex}.jpg"
                new_alert.image_snapshot.save(filename, ContentFile(decoded), save=False)

        # 5. Sauvegarde initiale pour générer un ID (nécessaire si on fait un clip)
        try:
            new_alert.save()
        except Exception as e:
            return JsonResponse(
                {"status": "error", "message": f"Could not create alert: {str(e)}"},
                status=400,
            )

        # 6. (Optionnel) si on veut générer un clip vidéo autour du timestamp
        if create_clip:
            from django.conf import settings
            clip_service = VideoClipService(settings.CAMERA_RTSP_URL)
            unix_ts = new_alert.timestamp.timestamp()
            clip_service.attach_clip_to_alert(new_alert, start_time=unix_ts, duration=10.0)

        # 7. Retourner l'ID créé
        return JsonResponse({"status": "success", "alert_id": new_alert.id}, status=201)


class RunYoloView(View):
    """
    Reçoit en POST une image Base64 (sans préfixe), lève un bool fall=True/False.
    """
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")

        base64_data = payload.get("image")
        if not base64_data:
            return JsonResponse({"error": "No image provided"}, status=400)

        try:
            # Ici, base64_data est la chaîne après la virgule (pure base64 jpeg)
            img_bytes = base64.b64decode(base64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Image décompressée est None")
        except Exception as e:
            return JsonResponse({"error": f"Invalid image data: {str(e)}"}, status=400)

        try:
            fall_detected, confidence = fall_service.detect_falls(img)
        except Exception as e:
            return JsonResponse({"error": f"YOLO inference error: {str(e)}"}, status=500)

        return JsonResponse({"fall": fall_detected, "confidence": confidence}, status=200)