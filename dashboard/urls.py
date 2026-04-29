from django.urls import path

from .views import dashboard_home, upload_csv

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("upload/", upload_csv, name="upload"),
]
