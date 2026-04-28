from django.shortcuts import redirect, render

from runs.models import PipelineRun

from .forms import PipelineRunForm


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
