from django.urls import path
from . import views

app_name = "detection"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("alerts/", views.AlertListView.as_view(), name="alerts"),
    path(
        "alerts/<int:pk>/acknowledge/",
        views.AcknowledgeAlertView.as_view(),
        name="acknowledge_alert",
    ),
    path("test/", views.TestDetectionView.as_view(), name="test_detection"),
    path("create-alert/", views.CreateAlertView.as_view(), name="create_alert"),
    path("run-yolo/", views.RunYoloView.as_view(), name="run_yolo"),
]