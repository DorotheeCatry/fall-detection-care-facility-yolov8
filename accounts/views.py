from django.views.generic import RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

class HomeRedirectView(LoginRequiredMixin, RedirectView):
    """
    Redirects authenticated users to the alerts page.

    If the user is not authenticated, they are redirected to the login page.
    Otherwise, they are redirected to the detection alerts page.
    """
    permanent = False
    url = reverse_lazy('detection:alerts')

    def get_redirect_url(self, *args, **kwargs):
        """
        Return the URL to redirect to.

        If the user is not authenticated, redirect to the login page.
        Otherwise, use the default redirect URL.
        """
        if not self.request.user.is_authenticated:
            return reverse_lazy('accounts:login')
        return super().get_redirect_url(*args, **kwargs)