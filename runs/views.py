from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import PipelineRun


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

    return render(
        request,
        "runs/run_detail.html",
        {
            "run": run,
            "dataset_artifacts": run.dataset_artifacts.order_by(
                "artifact_type", "symbol", "created_at"
            ),
            "model_artifacts": run.model_artifacts.order_by("model_type", "created_at"),
            "metric_snapshots": run.metric_snapshots.order_by("model_type", "created_at"),
            "report_artifacts": run.report_artifacts.order_by("report_type", "created_at"),
        },
    )
