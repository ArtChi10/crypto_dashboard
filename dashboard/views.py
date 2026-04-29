import pandas as pd
from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone

from mlcore.repositories import ArtifactRepository, DatasetRepository, ModelRepository
from mlcore.services import (
    BaselineTrainingService,
    CatBoostTrainingService,
    DatasetPreparationService,
    FullPipelineService,
    RunPersistenceService,
    RunPipelineUseCase,
)
from runs.models import PipelineRun

from .forms import CsvUploadForm, PipelineRunForm


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
            run = _create_upload_run(form.cleaned_data)
            try:
                raw_df = pd.read_csv(form.cleaned_data["csv_file"])
                _build_upload_use_case().execute(
                    run,
                    raw_df,
                    train_baseline=form.cleaned_data["train_baseline"],
                    train_catboost=form.cleaned_data["train_catboost"],
                )
            except Exception as exc:
                _mark_upload_run_failed(run, exc)
            return redirect("runs:detail", pk=run.pk)
    else:
        form = CsvUploadForm()

    return render(
        request,
        "dashboard/upload.html",
        {
            "form": form,
        },
    )


def _create_upload_run(cleaned_data):
    symbol = cleaned_data["symbol"]
    interval = cleaned_data["interval"]
    return PipelineRun.objects.create(
        name=f"Manual CSV upload {symbol} {interval}",
        status=PipelineRun.Status.CREATED,
        symbols_json=[symbol],
        interval=interval,
        start_date=cleaned_data["start_date"],
        end_date=cleaned_data["end_date"],
        target_horizon=cleaned_data["target_horizon"],
        initiated_by="manual_csv_upload",
    )


def _build_upload_use_case():
    artifact_repository = ArtifactRepository(settings.MEDIA_ROOT)
    dataset_repository = DatasetRepository()
    model_repository = ModelRepository()
    dataset_preparation_service = DatasetPreparationService(
        artifact_repository=artifact_repository,
        dataset_repository=dataset_repository,
    )
    baseline_training_service = BaselineTrainingService(
        artifact_repository=artifact_repository,
        model_repository=model_repository,
    )
    catboost_training_service = CatBoostTrainingService(
        artifact_repository=artifact_repository,
        model_repository=model_repository,
    )
    full_pipeline_service = FullPipelineService(
        dataset_preparation_service=dataset_preparation_service,
        baseline_training_service=baseline_training_service,
        catboost_training_service=catboost_training_service,
        dataset_repository=dataset_repository,
    )
    return RunPipelineUseCase(
        full_pipeline_service=full_pipeline_service,
        persistence_service=RunPersistenceService(),
    )


def _mark_upload_run_failed(run, exc):
    run.refresh_from_db()
    run.status = PipelineRun.Status.FAILED
    if run.started_at is None:
        run.started_at = timezone.now()
    run.finished_at = timezone.now()
    run.error_message = (str(exc) or exc.__class__.__name__)[:1000]
    run.save(update_fields=["status", "started_at", "finished_at", "error_message"])
