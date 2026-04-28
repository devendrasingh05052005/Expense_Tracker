from django.db import models
from django.contrib.auth.models import User

CATEGORY_CHOICES = [
    ('food', '🍔 Food & Dining'),
    ('travel', '✈️ Travel'),
    ('shopping', '🛍️ Shopping'),
    ('bills', '💡 Bills & Utilities'),
    ('health', '🏥 Health'),
    ('entertainment', '🎭 Entertainment'),
    ('others', '📦 Others'),
]

class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='others')
    date = models.DateField()
    merchant = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    receipt_file = models.FileField(upload_to='receipts/', null=True, blank=True)
    ocr_text = models.TextField(blank=True)  # raw OCR output stored for reference
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.title} – ${self.amount}"

    def get_category_display(self):
        """Return human-readable category name."""
        display_map = {
            'food': '🍔 Food & Dining',
            'travel': '✈️ Travel',
            'shopping': '🛍️ Shopping',
            'bills': '💡 Bills & Utilities',
            'health': '🏥 Health',
            'entertainment': '🎭 Entertainment',
            'others': '📦 Others',
        }
        return display_map.get(self.category, self.category.title())

    def get_category_display_icon(self):
        icons = {
            'food': '🍔', 'travel': '✈️', 'shopping': '🛍️',
            'bills': '💡', 'health': '🏥', 'entertainment': '🎭', 'others': '📦',
        }
        return icons.get(self.category, '📦')

