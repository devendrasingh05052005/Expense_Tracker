from django.core.exceptions import ValidationError
import mimetypes

def validate_receipt_file(value):
    # Allowed MIME types
    allowed_types = [
        'image/jpeg', 'image/png', 'image/webp',
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    ]
    # Max 10MB
    max_size = 10 * 1024 * 1024

    # Check size
    if value.size > max_size:
        raise ValidationError('File too large. Size should be less than 10MB.')

    # Check content type from filename/extension (simple, no extra dep)
    content_type, _ = mimetypes.guess_type(value.name)
    if content_type not in allowed_types:
        raise ValidationError(f'Unsupported file type: {value.name}. Allowed: JPG, PNG, WEBP, PDF, DOCX.')

