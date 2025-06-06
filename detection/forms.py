# detection/forms.py

from django import forms

class TestDetectionForm(forms.Form):
    upload_file = forms.FileField(
        label="Upload video/image for fall detection",
        help_text="Choose a short video or image file to run the model on.",
        widget=forms.FileInput(attrs={
            'accept': 'video/*,image/*',
            'class': 'sr-only',
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-input',
            'placeholder': 'Add details about this test...'
        })
    )
