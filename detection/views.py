"""
Views for the detection app.

This module contains class-based views for:
- Dashboard statistics and analytics
- Listing and filtering fall alerts
- Acknowledging and marking alert accuracy
- Test detection via file upload
- API endpoints for alert creation and YOLO inference (with throttling and snapshot/clip support)
"""

import os
import time
import json
import base64
import cv2
import numpy as np
import datetime
import uuid
from datetime import timedelta

from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, FormView, TemplateView, RedirectView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponseBadRequest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.db.models import Count, Avg, Q

from .models import FallAlert
from .forms import TestDetectionForm
from .services import FallDetectionService
from .services import VideoClipService

# Instantiate the fall detection service globally to avoid reloading the model on every request
fall_service = FallDetectionService(conf_threshold=0.70)

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Displays the dashboard with statistics and analytics for fall alerts.
    """
    template_name = "detection/dashboard.html"

    def get_context_data(self, **kwargs):
        """
        Gather statistics and analytics for the dashboard context.
        """
        context = super().get_context_data(**kwargs)
        
        # Get current time references
        now = timezone.now()
        today = now.date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        # Basic stats
        total_alerts = FallAlert.objects.count()
        today_alerts = FallAlert.objects.filter(timestamp__date=today).count()
        yesterday_alerts = FallAlert.objects.filter(timestamp__date=yesterday).count()
        pending_alerts = FallAlert.objects.filter(acknowledged=False).count()
        
        # Response rate calculation
        total_real_alerts = FallAlert.objects.exclude(detected_by="test_upload").count()
        acknowledged_alerts = FallAlert.objects.exclude(detected_by="test_upload").filter(acknowledged=True).count()
        response_rate = (acknowledged_alerts / total_real_alerts * 100) if total_real_alerts > 0 else 0
        
        # Model accuracy calculation
        accuracy_marked_alerts = FallAlert.objects.exclude(detected_by="test_upload").filter(is_accurate__isnull=False)
        total_marked = accuracy_marked_alerts.count()
        accurate_alerts = accuracy_marked_alerts.filter(is_accurate=True).count()
        model_accuracy = (accurate_alerts / total_marked * 100) if total_marked > 0 else None
        
        # Weekly activity (last 7 days)
        weekly_activity = []
        max_daily_count = 0
        for i in range(7):
            date = today - timedelta(days=i)
            count = FallAlert.objects.filter(timestamp__date=date).count()
            max_daily_count = max(max_daily_count, count)
            weekly_activity.append({
                'day': date.strftime('%a %m/%d'),
                'count': count,
                'date': date
            })
        weekly_activity.reverse()  # Show oldest to newest
        
        for stat in weekly_activity:
            stat['width'] = (stat['count'] / max_daily_count * 100) if max_daily_count > 0 else 0
        # Detection sources
        detection_sources = (
            FallAlert.objects
            .values('detected_by')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Add percentages
        for source in detection_sources:
            source['percentage'] = (source['count'] / total_alerts * 100) if total_alerts > 0 else 0
        
        # Recent alerts (last 10)
        recent_alerts = FallAlert.objects.select_related('acknowledged_by').order_by('-timestamp')[:10]
        
        # Additional stats
        avg_daily_alerts = FallAlert.objects.filter(
            timestamp__gte=week_ago
        ).count() / 7.0 if total_alerts > 0 else 0
        
        # Find peak hour - SQLite compatible version
        peak_hour = None
        if total_alerts > 0:
            # Get all alerts and group by hour in Python (SQLite compatible)
            alerts_with_hours = FallAlert.objects.all().values_list('timestamp', flat=True)
            hour_counts = {}
            for timestamp in alerts_with_hours:
                hour = timestamp.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            if hour_counts:
                peak_hour_num = max(hour_counts, key=hour_counts.get)
                peak_hour = f"{peak_hour_num:02d}:00"
        
        # Average response time (for acknowledged alerts)
        acknowledged_with_times = FallAlert.objects.filter(
            acknowledged=True,
            acknowledged_at__isnull=False
        )
        
        avg_response_time = None
        if acknowledged_with_times.exists():
            total_response_time = sum([
                (alert.acknowledged_at - alert.timestamp).total_seconds()
                for alert in acknowledged_with_times
            ])
            avg_response_seconds = total_response_time / acknowledged_with_times.count()
            avg_response_time = f"{int(avg_response_seconds // 60)}m {int(avg_response_seconds % 60)}s"
        
        # Get last alert time
        last_alert = FallAlert.objects.order_by('-timestamp').first()
        last_alert_time = last_alert.timestamp if last_alert else None
        
        context['stats'] = {
            'total_alerts': total_alerts,
            'today_alerts': today_alerts,
            'today_vs_yesterday': today_alerts - yesterday_alerts,
            'pending_alerts': pending_alerts,
            'response_rate': response_rate,
            'model_accuracy': model_accuracy,
            'total_marked_accuracy': total_marked,
            'weekly_activity': weekly_activity,
            'max_daily_alerts': max_daily_count,
            'detection_sources': detection_sources,
            'recent_alerts': recent_alerts,
            'avg_daily_alerts': avg_daily_alerts,
            'peak_hour': peak_hour,
            'avg_response_time': avg_response_time,
            'last_alert_time': last_alert_time,
        }
        
        return context

class AlertListView(LoginRequiredMixin, ListView):
    """
    Displays a paginated, filterable, and sortable list of fall alerts.
    """
    model = FallAlert
    template_name = "detection/alerts_list.html"
    context_object_name = "alerts"
    paginate_by = 20

    def get_queryset(self):
        """
        Return the filtered and sorted queryset for the alert list.
        """
        qs = super().get_queryset()
        if self.request.GET.get("include_tests") != "1":
            qs = qs.exclude(detected_by="test_upload")
        # Date filter
        date = self.request.GET.get("date")
        if date:
            qs = qs.filter(timestamp__date=date)
        hour = self.request.GET.get("hour")
        if hour:
            qs = qs.filter(timestamp__hour=hour.split(":")[0])
        detected_by = self.request.GET.getlist("detected_by")
        if detected_by:
            qs = qs.filter(detected_by__in=detected_by)
        status = self.request.GET.getlist("status")
        if status:
            if "acknowledged" in status and "new" not in status:
                qs = qs.filter(acknowledged=True)
            elif "new" in status and "acknowledged" not in status:
                qs = qs.filter(acknowledged=False)
        # Sorting
        sort = self.request.GET.get("sort")
        order = self.request.GET.get("order", "asc")
        if sort in ["timestamp", "detected_by", "yolo_confidence"]:
            if order == "desc":
                sort = "-" + sort
            qs = qs.order_by(sort)
        return qs

    def get_context_data(self, **kwargs):
        """
        Add filter options and selections to the context.
        """
        ctx = super().get_context_data(**kwargs)
        ctx["detected_by_options"] = FallAlert.objects.values_list("detected_by", flat=True).distinct()
        ctx["include_tests"] = (self.request.GET.get("include_tests") == "1")
        ctx["detected_by_selected"] = self.request.GET.getlist("detected_by")
        ctx["status_selected"] = self.request.GET.getlist("status")
        ctx["date_selected"] = self.request.GET.get("date", "")
        ctx["hour_selected"] = self.request.GET.get("hour", "")
        return ctx

class AcknowledgeAlertView(LoginRequiredMixin, RedirectView):
    """
    Marks an alert as acknowledged and optionally marks its accuracy.
    Redirects back to the alerts list.
    """
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        """
        Acknowledge the alert and optionally mark its accuracy.
        """
        alert = get_object_or_404(FallAlert, pk=kwargs["pk"])
        is_accurate = self.request.GET.get('accurate')
        
        # Always acknowledge the alert
        alert.acknowledged = True
        alert.acknowledged_by = self.request.user
        alert.acknowledged_at = timezone.now()
        
        # Set accuracy if specified
        if is_accurate is not None:
            alert.is_accurate = is_accurate == 'true'
            alert.accuracy_marked_by = self.request.user
            alert.accuracy_marked_at = timezone.now()
            
            accuracy_text = "accurate" if alert.is_accurate else "inaccurate"
            messages.success(self.request, f"Alert acknowledged and marked as {accuracy_text}.")
        else:
            messages.success(self.request, "Alert acknowledged successfully.")
        
        alert.save()
        return reverse_lazy("detection:alerts")

class TestDetectionView(LoginRequiredMixin, FormView):
    """
    Handles file uploads for test fall detection and displays results.
    """
    template_name = "detection/test_detection.html"
    form_class    = TestDetectionForm
    success_url   = reverse_lazy("detection:test_detection")

    def get_context_data(self, **kwargs):
        """
        Add processed image and detection results to the context.
        """
        context = super().get_context_data(**kwargs)
        # preserve your live-camera flag
        context["is_camera_enabled"] = True
        # injection points for the upload preview
        context["processed_image"] = kwargs.get("processed_image")
        context["fall_detected"]   = kwargs.get("fall_detected")
        context["confidence"]      = kwargs.get("confidence")
        return context

    def form_valid(self, form):
        """
        Process the uploaded file, run fall detection, and render results.
        """
        upload      = form.cleaned_data["upload_file"]
        description = form.cleaned_data.get("description", "")
        temp_path   = None

        try:
            # --- 1. save temp file so OpenCV can read it ---
            if hasattr(upload, "temporary_file_path"):
                temp_path = upload.temporary_file_path()
            else:
                import tempfile
                suffix = os.path.splitext(upload.name)[1]
                tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in upload.chunks():
                    tmp.write(chunk)
                tmp.flush(); tmp.close()
                temp_path = tmp.name

            # --- 2. read first frame ---
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

            # --- 3. run raw inference + boolean detection ---
            raw_results      = fall_service.run_model(frame)
            fall_detected, confidence = fall_service.detect_falls(frame)

            # --- 4. draw boxes & labels on a copy of the frame ---
            proc = frame.copy()
            for r in raw_results:
                for box in r.boxes:
                    # unpack xyxy Tensor → Python ints
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    cv2.rectangle(proc, (x1, y1), (x2, y2), (0, 0, 255), 2)

                    # safely cast confidence Tensor → float before formatting
                    cls_name = r.names[int(box.cls)]
                    conf     = float(box.conf)
                    label    = f"{cls_name}:{conf:.2f}"

                    cv2.putText(
                        proc,
                        label,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        1
                    )

            # --- 5. encode to base64 for template preview ---
            _, buf  = cv2.imencode('.jpg', proc)
            img_b64 = base64.b64encode(buf).decode()

            # --- 6. if fall → create test alert in DB ---
                # 1️⃣ create the alert record
            if fall_detected:
                alert = FallAlert.objects.create(
                    detected_by    = "test_upload",
                    description    = description or f"Test upload: {upload.name}",
                    yolo_confidence= confidence,
                    yolo_class     = "Fall-Detected",
                )
                # 2️⃣ persist the original frame as the snapshot
                alert.save_snapshot_from_frame(frame)
                alert.save()
                messages.success(self.request, "Fall detected ! Alerte créée.")
            else:
                messages.info(self.request, "Aucune chute détectée pour ce fichier.")

            # --- 7. render immediately with the preview card shown ---
            return render(
                self.request,
                self.template_name,
                self.get_context_data(
                    form            = form,
                    processed_image = img_b64,
                    fall_detected   = fall_detected,
                    confidence      = confidence * 100 if confidence else None
                )
            )

        except Exception as e:
            messages.error(self.request, f"Error processing upload: {e}")
            return super().form_valid(form)

        finally:
            if temp_path and not hasattr(upload, "temporary_file_path"):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

class CreateAlertView(LoginRequiredMixin, View):
    """
    API endpoint to create or update a FallAlert (live_camera alerts are throttled).
    Handles yolo_confidence, yolo_class, description, snapshot_b64, and video clip.
    """
    THRESHOLD = timedelta(seconds=30)

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to create or update a FallAlert.
        """
        # 1. Charger le JSON du body
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")

        alert_type   = payload.get("type", "live_camera")
        description  = payload.get("description", "")
        yolo_conf    = payload.get("yolo_confidence")
        yolo_cls     = payload.get("yolo_class", "")
        metadata     = payload.get("metadata")
        snapshot_b64 = payload.get("snapshot_b64")
        make_clip    = payload.get("make_clip", False)

        now = timezone.now()

        # 2. Si c'est un live_camera, voir si on dépasse le seuil de throttle
        if alert_type == "live_camera":
            last = (
                FallAlert.objects
                         .filter(detected_by="live_camera")
                         .order_by("-timestamp")
                         .first()
            )
            if last and (now - last.timestamp) < self.THRESHOLD:
                # réutiliser la même alerte
                alert = last
                alert.yolo_confidence = yolo_conf
                alert.yolo_class      = yolo_cls
                alert.description     = "Fall detected via YOLOv8"
                alert.metadata        = metadata
                alert.save()

                # snapshot, si fourni
                if snapshot_b64:
                    self._attach_snapshot(alert, snapshot_b64)

                # clip, si demandé
                if make_clip:
                    self._attach_clip(alert)

                return JsonResponse({"status":"updated","alert_id":alert.id}, status=200)

        # 3. Sinon, créer une nouvelle alerte
        alert = FallAlert(
            detected_by     = alert_type,
            description     = description or ("Fall detected via YOLOv8"
                                              if alert_type=="live_camera" else ""),
            yolo_confidence = yolo_conf,
            yolo_class      = yolo_cls,
            metadata        = metadata,
        )
        alert.save()

        # 4. Attacher snapshot
        if snapshot_b64:
            self._attach_snapshot(alert, snapshot_b64)

        # 5. Attacher clip vidéo si demandé
        if make_clip:
            self._attach_clip(alert)

        return JsonResponse({"status":"created","alert_id":alert.id}, status=201)

    def _attach_snapshot(self, alert: FallAlert, b64: str) -> None:
        """
        Decode base64 snapshot and save to alert.image_snapshot.
        """
        try:
            header, data = b64.split(",", 1)
            decoded = base64.b64decode(data)
        except (ValueError, TypeError):
            return

        filename = f"{uuid.uuid4().hex}.jpg"
        django_file = ContentFile(decoded, name=filename)
        alert.image_snapshot.save(filename, django_file, save=True)

    def _attach_clip(self, alert: FallAlert) -> None:
        """
        Use VideoClipService to attach a short video clip around alert.timestamp.
        """
        from django.conf import settings
        clip_service = VideoClipService(settings.CAMERA_RTSP_URL)
        ts = alert.timestamp.timestamp()
        clip_service.attach_clip_to_alert(alert, start_time=ts, duration=10.0)

class RunYoloView(View):
    """
    API endpoint to run YOLO inference on a base64 image and (optionally) create/update a live_camera alert.
    Throttles alert creation to avoid duplicates.
    """
    THRESHOLD_SECS = 30         # Do not create more than one alert every 30 seconds
    CACHE_KEY      = "last_live_alert_ts"

    def post(self, request, *args, **kwargs):
        """
        Handle POST request with base64 image, run YOLO inference, and manage alert creation.
        """
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")

        base64_data = payload.get("image")
        if not base64_data:
            return JsonResponse({"error": "No image provided"}, status=400)

        try:
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

        if not fall_detected:
            return JsonResponse({"fall": False}, status=200)

        now = timezone.now()
        last_ts = cache.get(self.CACHE_KEY)
        reuse = last_ts and (now.timestamp() - last_ts) < self.THRESHOLD_SECS

        if reuse:
            alert = (
                FallAlert.objects
                         .filter(detected_by="live_camera")
                         .order_by("-timestamp")
                         .first()
            )
            if alert:
                alert.yolo_confidence = confidence
                alert.save()
                alert.save_snapshot_from_frame(img)
                alert.save()
        else:
            alert = FallAlert.objects.create(
                detected_by     = "live_camera",
                description     = "Fall detected via YOLOv8",
                yolo_confidence = confidence,
                yolo_class      = "Fall-Detected",
            )
            alert.save_snapshot_from_frame(img)
            alert.save()
            cache.set(self.CACHE_KEY, now.timestamp(), timeout=None)

        return JsonResponse({"fall": True, "confidence": confidence}, status=200)