from django.core.exceptions import ValidationError
import moviepy.editor as mp  # You might need to install moviepy for this
from io import BytesIO

def validate_video_duration(value):
    try:
        # Read the uploaded file into memory using BytesIO
        file_data = value.read()
        video_file = BytesIO(file_data)
        
        # Use moviepy to read the video file from memory
        video = mp.VideoFileClip(video_file)
        
        # Validate the duration (you can set the limit as per your needs)
        max_duration = 60  # in seconds, for example
        if video.duration > max_duration:
            raise ValidationError(f"Video duration exceeds {max_duration} seconds.")
    except Exception as e:
        raise ValidationError(f"Invalid video file: {str(e)}")
