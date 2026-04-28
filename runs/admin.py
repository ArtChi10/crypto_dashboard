from django.contrib import admin

from .models import (
    DatasetArtifact,
    MetricSnapshot,
    ModelArtifact,
    PipelineRun,
    ReportArtifact,
)


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "status",
        "interval",
        "target_horizon",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "interval", "target_horizon", "created_at")
    search_fields = ("name", "initiated_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DatasetArtifact)
class DatasetArtifactAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "run",
        "artifact_type",
        "symbol",
        "file_path",
        "row_count",
        "created_at",
    )
    list_filter = ("artifact_type", "symbol", "created_at")
    search_fields = ("file_path", "symbol", "run__name")
    readonly_fields = ("created_at",)
    list_select_related = ("run",)


@admin.register(ModelArtifact)
class ModelArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "model_type", "file_path", "created_at")
    list_filter = ("model_type", "created_at")
    search_fields = ("file_path", "run__name")
    readonly_fields = ("created_at",)
    list_select_related = ("run",)


@admin.register(MetricSnapshot)
class MetricSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "run",
        "model_type",
        "accuracy",
        "f1",
        "roc_auc",
        "created_at",
    )
    list_filter = ("model_type", "created_at")
    search_fields = ("run__name",)
    readonly_fields = ("created_at",)
    list_select_related = ("run",)


@admin.register(ReportArtifact)
class ReportArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "report_type", "file_path", "created_at")
    list_filter = ("report_type", "created_at")
    search_fields = ("file_path", "run__name")
    readonly_fields = ("created_at",)
    list_select_related = ("run",)
