"""
URL configuration for the detection app.

Defines URL patterns for dashboard, alert management, test detection,
and API endpoints for alert creation and YOLO inference.
"""

from django.urls import path
from . import views

app_name = "detection"

urlpatterns = [
    # Dashboard view (main landing page for detection app)
    path("", views.DashboardView.as_view(), name="dashboard"),

    # List all alerts with filtering, sorting, and pagination
    path("alerts/", views.AlertListView.as_view(), name="alerts"),

    # Mark an alert as acknowledged (and optionally mark accuracy)
    path(
        "alerts/<int:pk>/acknowledge/",
        views.AcknowledgeAlertView.as_view(),
        name="acknowledge_alert",
    ),

    # Test detection page for uploading and running fall detection on files
    path("test/", views.TestDetectionView.as_view(), name="test_detection"),

    # API endpoint to create or update a FallAlert (used by frontend/camera)
    path("create-alert/", views.CreateAlertView.as_view(), name="create_alert"),

    # API endpoint to run YOLO inference on an image (returns fall result)
    path("run-yolo/", views.RunYoloView.as_view(), name="run_yolo"),
]