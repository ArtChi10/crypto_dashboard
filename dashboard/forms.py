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


class CsvUploadForm(forms.Form):
    csv_file = forms.FileField(label="CSV file")
    symbol = forms.CharField(
        label="Symbol",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "BTCUSDT"}),
    )
    interval = forms.CharField(
        label="Interval",
        initial="1h",
        max_length=50,
    )
    start_date = forms.DateField(
        label="Start date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        label="End date",
        required=False,
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
    train_catboost = forms.BooleanField(
        label="Train CatBoost",
        initial=True,
        required=False,
    )

    def clean_symbol(self):
        symbol = self.cleaned_data["symbol"].strip().upper()
        if not SYMBOL_PATTERN.fullmatch(symbol) or symbol.isdigit():
            raise forms.ValidationError("Используйте тикер вроде BTCUSDT.")
        return symbol

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Загрузите файл с расширением .csv.")
        return csv_file

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date не может быть раньше start date.")

        if end_date and end_date > timezone.localdate():
            self.add_error("end_date", "End date не может быть позже сегодняшней даты.")

        if not cleaned_data.get("train_baseline") and not cleaned_data.get("train_catboost"):
            raise forms.ValidationError("Выберите хотя бы одну модель для обучения.")

        return cleaned_data


class BinancePipelineForm(forms.Form):
    symbol = forms.CharField(
        label="Symbol",
        initial="BTCUSDT",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "BTCUSDT"}),
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
    train_catboost = forms.BooleanField(
        label="Train CatBoost",
        initial=True,
        required=False,
    )
    enable_forecast_replay = forms.BooleanField(
        label="Enable forecast replay",
        initial=False,
        required=False,
        help_text=(
            "Downloads candles after the selected end date and compares model direction "
            "predictions with actual future movement."
        ),
    )
    replay_steps = forms.IntegerField(
        label="Replay steps",
        initial=5,
        min_value=1,
        max_value=50,
        help_text="Number of future replay points to compare. Use 5 for a quick MVP check.",
    )

    def clean_symbol(self):
        symbol = self.cleaned_data["symbol"].strip().upper()
        if not SYMBOL_PATTERN.fullmatch(symbol) or symbol.isdigit():
            raise forms.ValidationError("Используйте тикер вроде BTCUSDT.")
        return symbol

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date не может быть раньше start date.")

        if end_date and end_date > timezone.localdate():
            self.add_error("end_date", "End date не может быть позже сегодняшней даты.")

        if not cleaned_data.get("train_baseline") and not cleaned_data.get("train_catboost"):
            raise forms.ValidationError("Выберите хотя бы одну модель для обучения.")

        return cleaned_data
