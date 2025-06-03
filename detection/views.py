from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .models import FallAlert
from .forms import TestDetectionForm
from django.utils import timezone

# Require login on all these views:
login_req = [method_decorator(login_required, name="dispatch")]


@method_decorator(login_required, name="dispatch")
class AlertListView(ListView):
    model = FallAlert
    template_name = "detection/alerts_list.html"
    context_object_name = "alerts"
    paginate_by = 20  # optional: paginate 20 per page


@login_required
def acknowledge_alert(request, pk):
    alert = get_object_or_404(FallAlert, pk=pk)
    alert.acknowledged = True
    alert.acknowledged_by = request.user
    alert.acknowledged_at = timezone.now()
    alert.save()
    return redirect("detection:alerts")


@method_decorator(login_required, name="dispatch")
class TestDetectionView(FormView):
    """
    A simple form to upload a short video or image,
    then (later) run the YOLOv8 model against it.
    """
    template_name = "detection/test_detection.html"
    form_class = TestDetectionForm
    success_url = reverse_lazy("detection:test_detection")

    def form_valid(self, form):
        # For now, just save the uploaded file to a temp location,
        # and create a dummy FallAlert to show in the alerts list.
        upload = form.cleaned_data["upload_file"]
        # Ideally: run your YOLOv8 inference here, produce one or more FallAlert instances.
        # For now, we'll just create a placeholder:
        FallAlert.objects.create(
            detected_by="test_upload",
            description=f"Test upload: {upload.name}",
        )
        return super().form_valid(form)
