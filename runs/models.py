from django.db import models


class PipelineRun(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    symbols_json = models.JSONField(default=list, blank=True)
    interval = models.CharField(max_length=50, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    target_horizon = models.PositiveIntegerField(null=True, blank=True)
    initiated_by = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class DatasetArtifact(models.Model):
    class ArtifactType(models.TextChoices):
        RAW = "raw", "Raw"
        PROCESSED = "processed", "Processed"
        FINAL = "final", "Final"

    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.CASCADE,
        related_name="dataset_artifacts",
    )
    artifact_type = models.CharField(max_length=20, choices=ArtifactType.choices)
    symbol = models.CharField(max_length=20, blank=True)
    file_path = models.CharField(max_length=500)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.artifact_type}: {self.file_path}"


class ModelArtifact(models.Model):
    class ModelType(models.TextChoices):
        DUMMY = "dummy", "Dummy"
        BASELINE = "baseline", "Baseline"
        CATBOOST = "catboost", "CatBoost"

    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.CASCADE,
        related_name="model_artifacts",
    )
    model_type = models.CharField(max_length=20, choices=ModelType.choices)
    file_path = models.CharField(max_length=500)
    params_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.model_type}: {self.file_path}"


class MetricSnapshot(models.Model):
    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.CASCADE,
        related_name="metric_snapshots",
    )
    model_type = models.CharField(max_length=20, choices=ModelArtifact.ModelType.choices)
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1 = models.FloatField(null=True, blank=True)
    roc_auc = models.FloatField(null=True, blank=True)
    confusion_matrix_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.model_type} metrics for {self.run}"


class ReportArtifact(models.Model):
    class ReportType(models.TextChoices):
        PRICE_PLOT = "price_plot", "Price plot"
        TARGET_DISTRIBUTION = "target_distribution", "Target distribution"
        FEATURE_IMPORTANCE = "feature_importance", "Feature importance"
        METRICS_PLOT = "metrics_plot", "Metrics plot"
        STABILITY_TABLE = "stability_table", "Stability table"
        STABILITY_PLOT = "stability_plot", "Stability plot"
        FORECAST_REPLAY = "forecast_replay", "Forecast replay"
        FORECAST_REPLAY_TABLE = "forecast_replay_table", "Forecast replay table"

    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.CASCADE,
        related_name="report_artifacts",
    )
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    file_path = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.report_type}: {self.file_path}"
