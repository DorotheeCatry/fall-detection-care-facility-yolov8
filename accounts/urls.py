from django.urls import path
from django.contrib.auth import views as auth_views

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path(
        # We don’t supply a template_name: LogoutView will immediately log out on GET
        "logout/",
        auth_views.LogoutView.as_view(next_page="accounts:login"),
        name="logout",
    ),
]

