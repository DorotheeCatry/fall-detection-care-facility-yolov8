"""
URL configuration for the backend project.

This module defines the root URL patterns for the Django project, including:
- Admin interface
- User accounts (login, logout, password reset)
- Detection app (fall detection dashboard and related views)
- Live reload for development (django-browser-reload)
- Static and media file serving in DEBUG mode

For more information, see:
https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

def redirect_to_dashboard(request):
    """
    Redirects the root URL to the detection dashboard.
    """
    return redirect('detection:dashboard')

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("", lambda request: redirect("detection:dashboard"), name="home"),  # Redirect root to dashboard
    path("detection/", include("detection.urls", namespace="detection")),
    # Add other app includes here as needed
    path("__reload__/", include("django_browser_reload.urls")),  # Live reload for development
]

# Serve media and static files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)