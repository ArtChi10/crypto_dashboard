import csv
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import PipelineRun

MEDIA_ARTIFACT_PREFIXES = ("datasets/", "models/", "reports/")
STABILITY_TABLE_REPORT_TYPE = "stability_table"
STABILITY_PREVIEW_LIMIT = 20
STABILITY_PREVIEW_COLUMNS = (
    "model_type",
    "period_start",
    "period_end",
    "rows",
    "accuracy",
    "f1",
    "roc_auc",
)
FORECAST_REPLAY_TABLE_REPORT_TYPE = "forecast_replay_table"
FORECAST_REPLAY_PREVIEW_LIMIT = 20


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
    report_presenters = [_report_artifact_presenter(artifact) for artifact in report_artifacts]

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
            "report_artifacts": report_presenters,
            "stability_table": _stability_table_preview(report_artifacts),
            "forecast_replay": _forecast_replay_preview(report_artifacts),
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


def _report_artifact_presenter(artifact):
    file_url = _media_url_for_path(artifact.file_path)

    return {
        "artifact": artifact,
        "file_url": file_url,
        "image_url": _report_image_url(artifact.file_path, file_url),
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


def _stability_table_preview(report_artifacts):
    stability_artifact = next(
        (
            artifact
            for artifact in report_artifacts
            if artifact.report_type == STABILITY_TABLE_REPORT_TYPE
        ),
        None,
    )
    if stability_artifact is None:
        return None

    preview = {
        "artifact": stability_artifact,
        "file_url": _media_url_for_path(stability_artifact.file_path),
        "columns": list(STABILITY_PREVIEW_COLUMNS),
        "rows": [],
        "truncated": False,
        "preview_unavailable": False,
    }
    csv_path = _safe_media_csv_path(stability_artifact.file_path)
    if csv_path is None:
        preview["preview_unavailable"] = True
        return preview
    if not csv_path.is_file():
        preview["preview_unavailable"] = True
        return preview

    try:
        with csv_path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for index, row in enumerate(reader):
                if index >= STABILITY_PREVIEW_LIMIT:
                    preview["truncated"] = True
                    break
                preview["rows"].append(_stability_row_presenter(row))
    except (OSError, csv.Error, UnicodeDecodeError):
        preview["rows"] = []
        preview["preview_unavailable"] = True

    return preview


def _stability_row_presenter(row):
    return {
        "model_type": row.get("model_type") or "-",
        "period_start": row.get("period_start") or "-",
        "period_end": row.get("period_end") or "-",
        "rows": row.get("rows") or "-",
        "accuracy": _format_csv_metric(row.get("accuracy")),
        "f1": _format_csv_metric(row.get("f1")),
        "roc_auc": _format_csv_metric(row.get("roc_auc")),
    }


def _forecast_replay_preview(report_artifacts):
    replay_artifact = next(
        (
            artifact
            for artifact in report_artifacts
            if artifact.report_type == FORECAST_REPLAY_TABLE_REPORT_TYPE
        ),
        None,
    )
    if replay_artifact is None:
        return None

    preview = {
        "artifact": replay_artifact,
        "file_url": _media_url_for_path(replay_artifact.file_path),
        "rows": [],
        "truncated": False,
        "preview_unavailable": False,
        "correct_count": None,
        "total_count": None,
        "hit_rate": None,
        "avg_probability": None,
    }
    csv_path = _safe_media_csv_path(replay_artifact.file_path)
    if csv_path is None:
        preview["preview_unavailable"] = True
        return preview
    if not csv_path.is_file():
        preview["preview_unavailable"] = True
        return preview

    try:
        with csv_path.open(newline="", encoding="utf-8") as csv_file:
            all_rows = list(csv.DictReader(csv_file))
    except (OSError, csv.Error, UnicodeDecodeError):
        preview["preview_unavailable"] = True
        return preview

    preview["truncated"] = len(all_rows) > FORECAST_REPLAY_PREVIEW_LIMIT
    preview["rows"] = [
        _forecast_replay_row_presenter(row) for row in all_rows[:FORECAST_REPLAY_PREVIEW_LIMIT]
    ]
    _populate_forecast_replay_summary(preview, all_rows)
    return preview


def _populate_forecast_replay_summary(preview, rows):
    total_count = len(rows)
    correct_count = sum(1 for row in rows if _forecast_replay_row_is_correct(row))
    probabilities = [
        probability
        for probability in (_optional_csv_float(row.get("predicted_probability")) for row in rows)
        if probability is not None
    ]

    preview["total_count"] = total_count
    preview["correct_count"] = correct_count
    preview["hit_rate"] = f"{correct_count / total_count * 100:.1f}" if total_count else None
    if probabilities:
        preview["avg_probability"] = f"{sum(probabilities) / len(probabilities):.4f}"


def _forecast_replay_row_presenter(row):
    result_label = _forecast_replay_result_label(row)
    return {
        "timestamp": row.get("timestamp") or "-",
        "close": _format_csv_metric(row.get("close")),
        "future_close": _format_csv_metric(row.get("future_close")),
        "predicted": row.get("predicted_label") or _direction_label(row.get("predicted_direction")),
        "actual": row.get("actual_label") or _direction_label(row.get("actual_direction")),
        "probability": _format_csv_metric(row.get("predicted_probability")),
        "result": result_label,
        "result_class": (
            "result-label--correct" if result_label == "correct" else "result-label--wrong"
        ),
        "actual_change_pct": _format_forecast_replay_percent(row),
    }


def _forecast_replay_result_label(row):
    result_label = str(row.get("result_label") or "").strip().lower()
    if result_label in {"correct", "wrong"}:
        return result_label
    return "correct" if _forecast_replay_row_is_correct(row) else "wrong"


def _forecast_replay_row_is_correct(row):
    result_label = str(row.get("result_label") or "").strip().lower()
    if result_label in {"correct", "wrong"}:
        return result_label == "correct"

    is_correct = row.get("is_correct")
    if is_correct not in (None, ""):
        return _csv_bool(is_correct)

    return str(row.get("predicted_direction")) == str(row.get("actual_direction"))


def _direction_label(value):
    normalized = str(value).strip()
    if normalized == "1":
        return "up"
    if normalized == "0":
        return "down"
    return "-"


def _format_forecast_replay_percent(row):
    value = _optional_csv_float(row.get("actual_change_pct"))
    if value is None:
        close = _optional_csv_float(row.get("close"))
        future_close = _optional_csv_float(row.get("future_close"))
        if close not in (None, 0) and future_close is not None:
            value = (future_close - close) / close * 100
    if value is None:
        return "-"
    return f"{value:.4f}%"


def _optional_csv_float(value):
    if value in (None, "", "None", "nan", "NaN"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _csv_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "correct"}


def _media_url_for_path(file_path):
    relative_path = _relative_media_path(file_path)
    if relative_path is None:
        return None
    if not any(relative_path.startswith(prefix) for prefix in MEDIA_ARTIFACT_PREFIXES):
        return None

    return f"{settings.MEDIA_URL.rstrip('/')}/{relative_path}"


def _safe_media_csv_path(file_path):
    relative_path = _relative_media_path(file_path)
    if relative_path is None:
        return None
    if not relative_path.startswith("reports/"):
        return None
    if not relative_path.lower().endswith(".csv"):
        return None

    path = (Path(settings.MEDIA_ROOT) / relative_path).resolve()
    try:
        path.relative_to(Path(settings.MEDIA_ROOT).resolve())
    except ValueError:
        return None
    return path


def _report_image_url(file_path, file_url):
    if file_url is None:
        return None

    relative_path = _relative_media_path(file_path)
    if relative_path is None:
        return None
    if not relative_path.startswith("reports/"):
        return None
    if not relative_path.lower().endswith(".png"):
        return None

    return file_url


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


def _format_csv_metric(value):
    if value in (None, "", "None", "nan", "NaN"):
        return "-"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


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
