from django.urls import path

from .views import dashboard_home, run_binance_pipeline, upload_csv

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("upload/", upload_csv, name="upload"),
    path("binance/", run_binance_pipeline, name="binance"),
]
