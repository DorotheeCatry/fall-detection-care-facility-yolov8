from django.views.generic import RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

class HomeRedirectView(LoginRequiredMixin, RedirectView):
    """Redirect authenticated users to the alerts page"""
    permanent = False
    url = reverse_lazy('detection:alerts')

    def get_redirect_url(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return reverse_lazy('accounts:login')
        return super().get_redirect_url(*args, **kwargs)