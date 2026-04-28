from django.urls import path

from .views import run_detail, run_list

app_name = "runs"

urlpatterns = [
    path("", run_list, name="list"),
    path("<int:pk>/", run_detail, name="detail"),
]
