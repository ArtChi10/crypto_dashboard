from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import PipelineRun

MEDIA_ARTIFACT_PREFIXES = ("datasets/", "models/", "reports/")


def run_list(request):
    runs = PipelineRun.objects.order_by("-created_at")
    paginator = Paginator(runs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "runs/run_list.html",
        {
            "page_obj": page_obj,
        },
    )


def run_detail(request, pk):
    run = get_object_or_404(PipelineRun, pk=pk)
    dataset_artifacts = run.dataset_artifacts.order_by("artifact_type", "symbol", "created_at")
    model_artifacts = run.model_artifacts.order_by("model_type", "created_at")
    metric_snapshots = run.metric_snapshots.order_by("model_type", "created_at")
    report_artifacts = run.report_artifacts.order_by("report_type", "created_at")

    return render(
        request,
        "runs/run_detail.html",
        {
            "run": run,
            "dataset_artifacts": [_artifact_presenter(artifact) for artifact in dataset_artifacts],
            "model_artifacts": [
                _model_artifact_presenter(artifact) for artifact in model_artifacts
            ],
            "metric_snapshots": [_metric_snapshot_presenter(metric) for metric in metric_snapshots],
            "report_artifacts": [_artifact_presenter(artifact) for artifact in report_artifacts],
        },
    )


def _artifact_presenter(artifact):
    return {
        "artifact": artifact,
        "file_url": _media_url_for_path(artifact.file_path),
    }


def _model_artifact_presenter(artifact):
    params = artifact.params_json or {}
    feature_columns = params.get("feature_columns")
    feature_count = len(feature_columns) if isinstance(feature_columns, list) else None

    return {
        "artifact": artifact,
        "file_url": _media_url_for_path(artifact.file_path),
        "train_rows": params.get("train_rows"),
        "valid_rows": params.get("valid_rows"),
        "test_rows": params.get("test_rows"),
        "feature_count": feature_count,
    }


def _metric_snapshot_presenter(metric):
    return {
        "metric": metric,
        "accuracy": _format_metric(metric.accuracy),
        "precision": _format_metric(metric.precision),
        "recall": _format_metric(metric.recall),
        "f1": _format_metric(metric.f1),
        "roc_auc": _format_metric(metric.roc_auc),
        "confusion_matrix": _format_confusion_matrix(metric.confusion_matrix_json),
    }


def _media_url_for_path(file_path):
    relative_path = _relative_media_path(file_path)
    if relative_path is None:
        return None
    if not any(relative_path.startswith(prefix) for prefix in MEDIA_ARTIFACT_PREFIXES):
        return None

    return f"{settings.MEDIA_URL.rstrip('/')}/{relative_path}"


def _relative_media_path(file_path):
    raw_path = str(file_path or "").strip()
    if not raw_path:
        return None

    path = Path(raw_path)
    if path.is_absolute():
        try:
            relative_path = path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())
        except ValueError:
            return None
        normalized_path = relative_path.as_posix()
    else:
        normalized_path = raw_path.replace("\\", "/").lstrip("/")

    pure_path = PurePosixPath(normalized_path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return None

    return pure_path.as_posix()


def _format_metric(value):
    if value is None:
        return None
    return f"{float(value):.4f}"


def _format_confusion_matrix(matrix):
    if not matrix:
        return None
    if isinstance(matrix, list):
        rows = []
        for row in matrix:
            if isinstance(row, list):
                rows.append("[ " + "  ".join(str(value) for value in row) + " ]")
            else:
                rows.append(str(row))
        return "\n".join(rows)
    return str(matrix)
