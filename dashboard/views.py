from django.shortcuts import redirect, render

from mlcore.services import CsvPipelineUploadUseCase
from mlcore.services.binance_pipeline_use_case import BinancePipelineUseCase
from runs.models import PipelineRun

from .forms import BinancePipelineForm, CsvUploadForm, PipelineRunForm


def dashboard_home(request):
    if request.method == "POST":
        form = PipelineRunForm(request.POST)
        if form.is_valid():
            symbols = form.cleaned_data["symbols"]
            interval = form.cleaned_data["interval"]
            run = PipelineRun.objects.create(
                name=f"Pipeline run {', '.join(symbols)} {interval}",
                status=PipelineRun.Status.CREATED,
                symbols_json=symbols,
                interval=interval,
                start_date=form.cleaned_data["start_date"],
                end_date=form.cleaned_data["end_date"],
                target_horizon=form.cleaned_data["target_horizon"],
            )
            return redirect("runs:detail", pk=run.pk)
    else:
        form = PipelineRunForm()

    latest_runs = PipelineRun.objects.order_by("-created_at")[:10]
    total_runs = PipelineRun.objects.count()

    return render(
        request,
        "dashboard/dashboard.html",
        {
            "form": form,
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
