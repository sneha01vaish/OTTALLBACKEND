from django.db import models
from django.contrib.auth.models import User
from .Validators import validate_video_duration, ValidationError
from datetime import timedelta, datetime
import random
from django.utils import timezone 


STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published')
    ]
    

class Movie(models.Model):
    title = models.CharField(max_length=255)
    genre = models.CharField(max_length=100)
    language = models.CharField(max_length=50)
    release_date = models.DateField()
    cast_and_crew = models.TextField()  # Or you can use a separate table to store this\\\\\\\\\\\\\\\\
    synopsis = models.TextField()
    trailer_url = models.URLField(max_length=500)
    movie_file = models.FileField(upload_to='movies/')
    poster_image = models.ImageField(upload_to='posters/')
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    is_trending = models.BooleanField(default=False)


    def __str__(self):
        return self.title

class Show(models.Model):
    title = models.CharField(max_length=255)
    genre = models.CharField(max_length=100)
    language = models.CharField(max_length=50)
    release_date = models.DateField()
    synopsis = models.TextField()
    trailer_url = models.URLField(max_length=500)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    poster_image = models.ImageField(upload_to='show_posters/')
    show_file = models.FileField(upload_to='shows/')
    is_trending = models.BooleanField(default=False)


    def __str__(self):
        return self.title

class LiveNews(models.Model):
    title = models.CharField(max_length=255)
    youtube_url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    
class Plan(models.Model):
    plan_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.TextField()
    duration = models.IntegerField()  # duration in days

    def __str__(self):
        return self.plan_name
class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.plan.plan_name}"
        
class Payment(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=[('card', 'Card'), ('upi', 'UPI')], default='card')
    payment_status = models.CharField(max_length=20, default='pending')
    payment_date = models.DateTimeField(auto_now_add=True)
    # razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    # razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    # razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.subscription.user.username} - {self.amount} ({self.payment_status})"
        # -------------------shorts video api----------------------
class ShortVideo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video_file = models.FileField(upload_to='short_videos/', validators=[validate_video_duration])
    title = models.CharField(max_length=255)
    upload_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

    def validate_video_duration(value):
        # You can add video duration validation here (e.g., not more than 1 minute).
        if value.duration > 60:
            raise ValidationError("Video duration cannot exceed 1 minute.")

def validate_image_size(image):
    max_size_kb = 500  # Max size in KB
    if image.size > max_size_kb * 1024:
        raise ValidationError(f"Image file too large (maximum size is {max_size_kb} KB)")

class Ad(models.Model):
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='ads/', validators=[validate_image_size])
    status = models.CharField(max_length=10, choices=(('Active', 'Active'), ('Inactive', 'Inactive')))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    def generate_otp(self):
        self.otp = str(random.randint(100000, 999999))
        self.otp_created_at = datetime.now()
        self.save()


    def is_otp_valid(self):
        return timezone.now() < self.otp_created_at + timedelta(minutes=10)

    def __str__(self):
        return self.user.username