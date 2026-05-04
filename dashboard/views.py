from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from mlcore.services import CsvPipelineUploadUseCase
from mlcore.services.binance_pipeline_use_case import BinancePipelineUseCase
from runs.models import PipelineRun

from .forms import BinancePipelineForm, CsvUploadForm


@require_safe
def dashboard_home(request):
    latest_runs = PipelineRun.objects.order_by("-created_at")[:10]
    total_runs = PipelineRun.objects.count()

    return render(
        request,
        "dashboard/dashboard.html",
        {
            "latest_runs": latest_runs,
            "total_runs": total_runs,
        },
    )


def upload_csv(request):
    if request.method == "POST":
        form = CsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            result = _build_csv_pipeline_upload_use_case().execute(
                csv_file=form.cleaned_data["csv_file"],
                symbol=form.cleaned_data["symbol"],
                interval=form.cleaned_data["interval"],
                start_date=form.cleaned_data["start_date"],
                end_date=form.cleaned_data["end_date"],
                target_horizon=form.cleaned_data["target_horizon"],
                train_baseline=form.cleaned_data["train_baseline"],
                train_catboost=form.cleaned_data["train_catboost"],
            )
            if result.run is not None:
                return redirect("runs:detail", pk=result.run.pk)

            form.add_error(None, result.error_message or "Не удалось обработать CSV.")
    else:
        form = CsvUploadForm()

    return render(
        request,
        "dashboard/upload.html",
        {
            "form": form,
        },
    )


def run_binance_pipeline(request):
    if request.method == "POST":
        form = BinancePipelineForm(request.POST)
        if form.is_valid():
            result = _build_binance_pipeline_use_case().execute(
                symbol=form.cleaned_data["symbol"],
                interval=form.cleaned_data["interval"],
                start_date=form.cleaned_data["start_date"],
                end_date=form.cleaned_data["end_date"],
                target_horizon=form.cleaned_data["target_horizon"],
                train_baseline=form.cleaned_data["train_baseline"],
                train_catboost=form.cleaned_data["train_catboost"],
            )
            if result.run is not None:
                return redirect("runs:detail", pk=result.run.pk)

            form.add_error(None, result.error_message or "Не удалось запустить Binance pipeline.")
    else:
        form = BinancePipelineForm()

    return render(
        request,
        "dashboard/binance.html",
        {
            "form": form,
        },
    )


def _build_csv_pipeline_upload_use_case():
    return CsvPipelineUploadUseCase()


def _build_binance_pipeline_use_case():
    return BinancePipelineUseCase()
