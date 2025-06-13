"""
Forms for the detection app.

This module defines forms used for uploading files and providing descriptions
for test fall detection runs.
"""

from django import forms

class TestDetectionForm(forms.Form):
    """
    Form for uploading a video or image file to test fall detection,
    with an optional description field.
    """
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
