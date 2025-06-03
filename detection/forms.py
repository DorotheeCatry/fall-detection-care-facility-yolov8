from django import forms

class TestDetectionForm(forms.Form):
    upload_file = forms.FileField(
        label="Upload video/image for fall detection",
        help_text="Choose a short video or image file to run the model on."
    )
