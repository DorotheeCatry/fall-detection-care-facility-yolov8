from django.shortcuts import render

# Create your views here.
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

@login_required
def home_redirect(request):
    return redirect("detection:alerts")
