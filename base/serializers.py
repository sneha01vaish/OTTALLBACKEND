from django.core.exceptions import ValidationError
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework.validators import ValidationError
from django.contrib.auth.models import User
from .models import Movie, Plan, Subscription, ShortVideo, Payment, Show, LiveNews, UserProfile
from datetime import timedelta
from django.utils import timezone
from .models import Ad


UserModel = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ['email', 'phone_number']

    def create(self, validated_data):
        user = User.objects.create(username=validated_data.get('email') or validated_data.get('phone_number'))
        profile = UserProfile.objects.create(user=user, phone_number=validated_data.get('phone_number'))
        profile.generate_otp()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise ValidationError('Invalid credentials')
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'username']
        
        
class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'
        extra_kwargs = {
            'movie_file': {'required': False},
            'poster_image': {'required': False},
        }
class ShowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Show
        fields = '__all__'
        
class LiveNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiveNews
        fields = '__all__'



class UserListSerializer(serializers.ModelSerializer):
    subscription_status = serializers.SerializerMethodField()
    last_active = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'subscription_status', 'last_active']

    def get_subscription_status(self, obj):
        # Assuming Subscription model is related to User
        try:
            return obj.profile.subscription.status  # Replace with correct field
        except AttributeError:
            return 'No Subscription'

    def get_last_active(self, obj):
        return obj.last_login or 'Never logged in'

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'
        
class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['plan']  # Only accept the plan in the request
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        plan = validated_data['plan']
        start_date = timezone.now().date()  # Set the start date to the current date
        end_date = start_date + timedelta(days=plan.duration)  # Calculate the end date
        
        # Create the subscription object
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True  # Activate the subscription
        )
        
        return subscription


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
class ShortVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShortVideo
        fields = ['id', 'title', 'video_file', 'upload_date']
        extra_kwargs = {
            'upload_date': {'read_only': True}
        }
        
class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = ['id', 'title', 'image', 'status', 'created_at']
        read_only_fields = ['created_at']
    
    def validate_image(self, value):
        # Ensure the image is smaller than 500KB
        if value.size > 500 * 1024:
            raise serializers.ValidationError("Image size must be less than 500KB.")
        return value