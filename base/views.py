from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import permissions, status
from rest_framework import status, viewsets
from .serializers import UserListSerializer, MovieSerializer, PlanSerializer, SubscriptionSerializer, RegistrationSerializer, ShortVideoSerializer, PaymentSerializer, ShowSerializer, LiveNewsSerializer, AdSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Plan, Subscription, Movie, ShortVideo, Payment, Show, LiveNews, Ad, UserProfile
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from rest_framework import generics
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from twilio.rest import Client
import razorpay
from django.conf import settings
import logging


import random


logger = logging.getLogger(__name__)



# Create your views here.
def send_sms(phone_number, otp):
    # Twilio credentials
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    twilio_phone_number = settings.TWILIO_PHONE_NUMBER

    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body=f'Your OTP code is {otp}',
        from_=twilio_phone_number,
        to=phone_number
    )

    return message.sid  # You can log or return this for debugging purposes
@api_view(['POST'])
@csrf_exempt
@permission_classes([AllowAny])
def test_email(request):
    data = request.data
    email = data.get('email')  # Ensure email is provided in the request data
    
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)

    # Check if a user with the same email (username) already exists
    if User.objects.filter(username=email).exists():
        return JsonResponse({'error': 'Email is already registered.'}, status=400) 

    # Create user with the provided email
    user = User.objects.create(username=email, email=email)

    # Generate OTP (6 digits)
    otp = random.randint(100000, 999999)

    # Create a UserProfile and assign the OTP
    profile = UserProfile.objects.create(user=user, otp=otp)

    try:
        # Send OTP to email
        send_mail(
            'Your OTP Code',
            f'Your OTP code is {otp}.',  # Send generated OTP
            settings.EMAIL_HOST_USER,     # Email sender (as per settings)
            [email],                      # Recipient's email address
            fail_silently=False,
        )
    except Exception as e:
        # Return error if email fails to send
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'message': 'OTP sent successfully', 'otp': otp}, status=200)

@api_view(['POST'])
@permission_classes([AllowAny])
def Register(request):
    data = request.data
    email = data.get('email')
    phone = data.get('phone_number')

    if not email and not phone:
        return JsonResponse({'error': 'Either email or phone number is required.'}, status=400)

    if email:
        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Email is already registered.'}, status=400)
        user = User.objects.create(username=email, email=email, is_active=False)  # Create inactive user

    elif phone:
        if UserProfile.objects.filter(phone_number=phone).exists():
            return JsonResponse({'error': 'Phone number is already registered.'}, status=400)
        user = User.objects.create(username=phone, is_active=False)  # Create inactive user

    profile = UserProfile.objects.create(user=user, phone_number=phone if phone else None)
    profile.generate_otp()  # Generate OTP

    # Send OTP
    if email:
        send_mail(
            'Your OTP Code',
            f'Your OTP code is {profile.otp}.',
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )
    elif phone:
        send_sms(phone, profile.otp)

    return JsonResponse({'message': 'OTP sent. Please verify to complete registration.'}, status=200)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    data = request.data
    email_or_phone = data.get('email_or_phone')
    otp = data.get('otp')

    # Ensure that email_or_phone and otp are provided
    if not email_or_phone or not otp:
        return JsonResponse({'error': 'email_or_phone and otp are required fields.'}, status=400)

    try:
        if '@' in email_or_phone:  # If it's an email
            user = User.objects.get(email=email_or_phone)
        else:  # If it's a phone number
            profile = UserProfile.objects.get(phone_number=email_or_phone)
            user = profile.user

        profile = UserProfile.objects.get(user=user)

        # Check if OTP matches and is still valid
        if profile.otp == otp and profile.is_otp_valid():
            profile.is_verified = True
            profile.save()
            return JsonResponse({'message': 'OTP verified successfully. User registered.'})
        else:
            return JsonResponse({'error': 'Invalid or expired OTP.'}, status=400)

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    try:
        email_or_phone = request.data.get('email_or_phone')

        if not email_or_phone:
            return Response({'error': 'Email or phone number is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine if the user provided an email or phone number
        if '@' in email_or_phone:
            # If email, look for the UserProfile by email
            profile = UserProfile.objects.get(user__email=email_or_phone)
        else:
            # If phone number, look for the UserProfile by phone number
            profile = UserProfile.objects.get(phone_number=email_or_phone)

        # Generate a new OTP
        new_otp = random.randint(100000, 999999)
        profile.otp = new_otp
        profile.save()

        # Optionally, send the OTP via email/SMS depending on the medium provided

        return Response({'message': 'OTP resent successfully', 'otp': new_otp}, status=status.HTTP_200_OK)

    except UserProfile.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        # Log the exact error
        logger.error(f"Error during resend OTP: {str(e)}", exc_info=True)
        return Response({'error': 'Internal Server Error. Please check the logs for details.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    try:
        email_or_phone = request.data.get('email_or_phone')
        otp = request.data.get('otp')

        # Debugging statements
        print(f"Received email_or_phone: {email_or_phone}, otp: {otp}")

        if not email_or_phone or not otp:
            return Response({'error': 'Email/Phone and OTP are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine if it's an email or phone
        if '@' in email_or_phone:
            # If email, look for the UserProfile by filtering through the User model's email
            profile = UserProfile.objects.get(user__email=email_or_phone)
        else:
            # If phone number, look for the UserProfile by phone number
            profile = UserProfile.objects.get(phone_number=email_or_phone)

        # Check OTP validity
        if profile.otp == otp and profile.is_otp_valid():
            refresh = RefreshToken.for_user(profile.user)
            access_token = refresh.access_token
            return Response({'message': 'Login successful','access_token': str(access_token), 'refresh_token': str(refresh)}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid OTP or OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

    except UserProfile.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        # Log the exact error
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        return Response({'error': 'Internal Server Error. Please check the logs for details.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class MovieViewSet(ModelViewSet):
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    parser_classes = (MultiPartParser, FormParser) 


@api_view(['GET'])
def user_list(request):
    # Fetch all users
    users = User.objects.all()

    # Serialize the users
    serializer = UserListSerializer(users, many=True)

    return Response(serializer.data, status=status.HTTP_200_OK)


# For blocking and deleting users
@api_view(['POST'])
def user_action(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    action = request.data.get('action', None)
    
    if action == 'block':
        user.profile.status = 'blocked'  # Assuming a status field in Profile model
        user.save()
        return Response({"message": "User blocked"}, status=status.HTTP_200_OK)

    elif action == 'delete':
        user.delete()
        return Response({"message": "User deleted"}, status=status.HTTP_200_OK)

    else:
        return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
    
    
@api_view(['GET'])
def user_detail(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        profile = user.profile  # assuming a related Profile model for additional user info

        user_data = {
            "profile_info": {
                "name": user.username,
                "email": user.email,
                "phone_number": profile.phone_number,
            },
            "subscription_details": {
                "plan": profile.subscription_plan.name,  # assuming plan exists in Profile
                "renewal_date": profile.renewal_date,
                "payment_history": profile.payment_history,  # assuming stored as a list or related model
            },
            "watch_history": profile.watch_history,  # assuming stored as a list
            "engagement_stats": profile.engagement_stats,  # assuming stored as a list
        }

        return Response(user_data, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


class PlanViewSet(ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    
class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def subscribe(self, request, pk=None):
        user = request.user
        plan = Plan.objects.get(pk=pk)
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=plan.duration)
        
        # Create the subscription
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True  # Mark it as active
        )
        
        return Response({'message': 'Subscription created'}, status=status.HTTP_201_CREATED)

# ----------payment===
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        subscription = Subscription.objects.get(pk=pk)
        payment_method = request.data.get('payment_method')
        payment = Payment.objects.create(
            subscription=subscription, 
            amount=subscription.plan.price, 
            payment_method=payment_method, 
            payment_status='success'
        )
        subscription.is_active = True
        subscription.save()
        return Response({'message': 'Payment successful'}, status=status.HTTP_200_OK)
# Upload short video
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_short_video(request):
    serializer = ShortVideoSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# List all short videos of a user
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_user_videos(request):
    videos = ShortVideo.objects.filter(user=request.user)
    serializer = ShortVideoSerializer(videos, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

# Delete short video
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_short_video(request, video_id):
    try:
        video = ShortVideo.objects.get(id=video_id, user=request.user)
        video.delete()
        return Response({"message": "Video deleted successfully."}, status=status.HTTP_200_OK)
    except ShortVideo.DoesNotExist:
        return Response({"error": "Video not found or you don't have permission to delete this video."}, status=status.HTTP_404_NOT_FOUND)
    
    
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
class ShowViewSet(viewsets.ModelViewSet):
    queryset = Show.objects.all()
    serializer_class = ShowSerializer
    
class TrendingMoviesView(generics.ListAPIView):
    queryset = Movie.objects.filter(is_trending=True)
    serializer_class = MovieSerializer

class TrendingShowsView(generics.ListAPIView):
    queryset = Show.objects.filter(is_trending=True)
    serializer_class = ShowSerializer

class LiveNewsViewSet(viewsets.ModelViewSet):
    queryset = LiveNews.objects.filter(is_active=True)
    serializer_class = LiveNewsSerializer


# def create_order(request, plan_id):
#     if request.method == 'POST':
#         # Get the plan
#         plan = Plan.objects.get(id=plan_id)
#         # Create a new subscription for the user
#         subscription = Subscription.objects.create(
#             user=request.user,
#             plan=plan,
#             start_date=datetime.now(),
#             is_active=False
#         )
#         # Create a Razorpay order
#         order_amount = int(plan.price * 100)  # Amount in paise
#         order_currency = 'INR'
#         order_receipt = f'order_rcptid_{subscription.id}'
#         razorpay_order = client.order.create({
#             'amount': order_amount,
#             'currency': order_currency,
#             'receipt': order_receipt,
#             'payment_capture': '1'
#         })
#         # Save the Razorpay order ID
#         payment = Payment.objects.create(
#             subscription=subscription,
#             amount=plan.price,
#             payment_method=request.POST.get('payment_method'),
#             razorpay_order_id=razorpay_order['id'],
#             payment_status='pending'
#         )

#         # Return order details to frontend
#         return JsonResponse({
#             'razorpay_order_id': razorpay_order['id'],
#             'amount': order_amount,
#             'currency': order_currency,
#             'key': settings.RAZORPAY_KEY_ID,
#             'subscription_id': subscription.id
#         })
# @csrf_exempt
# def verify_payment(request):
#     if request.method == "POST":
#         data = request.POST
#         try:
#             # Verify the payment signature
#             client.utility.verify_payment_signature({
#                 'razorpay_order_id': data['razorpay_order_id'],
#                 'razorpay_payment_id': data['razorpay_payment_id'],
#                 'razorpay_signature': data['razorpay_signature']
#             })
            
#             # Update payment and subscription status
#             payment = Payment.objects.get(razorpay_order_id=data['razorpay_order_id'])
#             payment.razorpay_payment_id = data['razorpay_payment_id']
#             payment.razorpay_signature = data['razorpay_signature']
#             payment.payment_status = 'success'
#             payment.save()
            
#             # Activate the subscription
#             payment.subscription.is_active = True
#             payment.subscription.save()
            
#             return JsonResponse({'status': 'Payment verified successfully.'})
#         except razorpay.errors.SignatureVerificationError:
#             return JsonResponse({'status': 'Payment verification failed.'}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Only authenticated users (owners) can upload ads
def upload_ad(request):
    parser_classes = (MultiPartParser, FormParser)
    serializer = AdSerializer(data=request.data)
    
    if serializer.is_valid():
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Any user can view ads
@api_view(['GET'])
@permission_classes([AllowAny])
def list_ads(request):
    ads = Ad.objects.all().order_by('-created_at')  # Display most recent ads first
    serializer = AdSerializer(ads, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)