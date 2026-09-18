from django import forms
from .models import Task

class TaskCreateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'target_group', 'priority', 'due_date', 'privacy']


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label='学生CSVファイル',
        help_text='UTF-8またはShift-JISのCSV形式'
    )

class UserCSVUploadForm(forms.Form):
    """管理画面用：教職員ユーザーCSV取り込みフォーム"""
    csv_file = forms.FileField(
        label="ユーザーCSVファイル",
        widget=forms.FileInput(attrs={'accept': '.csv'})
    )