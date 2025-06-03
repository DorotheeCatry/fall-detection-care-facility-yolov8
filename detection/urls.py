from django.urls import path
from detection import views

app_name = "detection"

urlpatterns = [
    # List all open or recent alerts
    path("alerts/", views.AlertListView.as_view(), name="alerts"),
    # A view to acknowledge one alert
    path(
        "alerts/<int:pk>/acknowledge/",
        views.acknowledge_alert,
        name="acknowledge_alert",
    ),
    # Page to upload a test video/image to run through the model
    path("test/", views.TestDetectionView.as_view(), name="test_detection"),
]