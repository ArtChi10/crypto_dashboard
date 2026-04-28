import re

from django import forms
from django.utils import timezone

DEFAULT_SYMBOLS = "BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT"
SYMBOL_PATTERN = re.compile(r"^(?=.*[A-Z])[A-Z0-9]{2,20}$")


class PipelineRunForm(forms.Form):
    symbols = forms.CharField(
        label="Symbols",
        initial=DEFAULT_SYMBOLS,
        help_text="Введите тикеры через запятую.",
        widget=forms.TextInput(attrs={"placeholder": "BTCUSDT, ETHUSDT"}),
    )
    interval = forms.CharField(
        label="Interval",
        initial="1h",
        max_length=50,
    )
    start_date = forms.DateField(
        label="Start date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        label="End date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    target_horizon = forms.IntegerField(
        label="Target horizon",
        initial=3,
        min_value=1,
    )
    train_baseline = forms.BooleanField(
        label="Train baseline",
        initial=True,
        required=False,
    )
    train_main_model = forms.BooleanField(
        label="Train main model",
        initial=True,
        required=False,
    )

    def clean_symbols(self):
        symbols = [
            symbol.strip().upper()
            for symbol in self.cleaned_data["symbols"].split(",")
            if symbol.strip()
        ]

        if not symbols:
            raise forms.ValidationError("Укажите хотя бы один symbol.")

        invalid_symbols = [
            symbol for symbol in symbols if not SYMBOL_PATTERN.fullmatch(symbol) or symbol.isdigit()
        ]
        if invalid_symbols:
            raise forms.ValidationError(
                "Некорректный symbol: %(symbols)s. Используйте тикеры вроде BTCUSDT.",
                params={"symbols": ", ".join(invalid_symbols)},
            )

        return symbols

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date не может быть раньше start date.")

        if end_date and end_date > timezone.localdate():
            self.add_error("end_date", "End date не может быть позже сегодняшней даты.")

        return cleaned_data
