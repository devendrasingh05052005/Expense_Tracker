from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Expense, CATEGORY_CHOICES
from .validators import validate_receipt_file
import datetime

class RegisterForm(UserCreationForm):
    email      = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name  = forms.CharField(max_length=50, required=False)

    class Meta:
        model  = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']


class ExpenseForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=datetime.date.today,
    )

    class Meta:
        model  = Expense
        fields = ['title', 'amount', 'category', 'date', 'merchant', 'notes', 'receipt_file']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ReceiptUploadForm(forms.Form):
    file = forms.FileField(
        label='Receipt Document',
        validators=[validate_receipt_file],
        help_text='Upload JPG, PNG, PDF or DOCX receipt (max 10MB).',
    )


class ExpenseFilterForm(forms.Form):
    category   = forms.ChoiceField(choices=[('', 'All Categories')] + CATEGORY_CHOICES, required=False)
    date_from  = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    date_to    = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    amount_min = forms.DecimalField(min_value=0, required=False)
    amount_max = forms.DecimalField(min_value=0, required=False)
    search     = forms.CharField(max_length=100, required=False)
