import os
import datetime
import random
import traceback
import logging
import re
import razorpay

from datetime import date, timedelta, timezone
from django.db.models.functions import TruncDate
from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum

from rest_framework import filters, generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser 
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
logger = logging.getLogger(__name__)

from .models import (
    AdminPaymentMethod, AdminProfile, BlockedUser, NotificationSettings, ProfileLike, UserPreferences, SupportMessage,
     UserSubscription, ReportedProblem,
    Profile, ProfileImage, Advertisement, FavouriteProfile,
    Notification, Comment, ChatRoom, Message, AadhaarVerification,SuccessStory, SubscriptionPlan, Payment,
)
from .serializers import (
    AdminCreateUserSerializer, AdminProfileDetailSerializer, AdminProfileListSerializer, AdminUserListSerializer, 
    BlockedUserSerializer, NotificationSettingsSerializer, UserPreferencesSerializer, SupportMessageSerializer,
    NotificationSettingSerializer, UserSubscriptionSerializer, ReportedProblemSerializer,
    BasicDetailsSerializer, EducationCareerSerializer, LocationSerializer,
    PersonalDetailsSerializer, RegisterSerializer, ReligionSerializer,
    ResetPasswordSerializer, SendOTPSerializer, VerifyOTPSerializer,
    CustomTokenObtainPairSerializer, UpdateProfileTypeSerializer, ProfileSerializer,
    ProfileLikeSerializer, FavouriteProfileSerializer, AdminProfileSerializer,
    SettingsProfileUpdateSerializer, AdvertisementSerializer, AadhaarVerificationSerializer,
    NotificationSerializer, CommentSerializer, ChatRoomSerializer, MessageSerializer,SuccessStorySerializer, SubscriptionPlanSerializer, AdminPaymentSerializer
)

User = get_user_model()

# ==================== AUTH & LOGIN VIEWS ====================

class LoginView(TokenObtainPairView): 
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "Account created successfully",
                "user_id": user.id,
                "email": user.email,
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetUserView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile_exists = hasattr(user, 'profile')
        return Response({
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "profile_type": user.profile_type,
            "profile_completed": profile_exists and user.profile.is_completed
        })

# ==================== MULTI-STEP PROFILE CREATION VIEWS ====================

class UpdateProfileTypeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UpdateProfileTypeSerializer(request.user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            profile, _ = Profile.objects.get_or_create(user=request.user)
            profile.current_step = 1
            profile.save()
            return Response({"message": "Profile type updated", "step": 1})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateBasicDetailsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        data = request.data.copy()

        if data.get('profile_type') == 'parent':
            data['full_name'] = data.get('child_name')

        serializer = BasicDetailsSerializer(profile, data=data, partial=True)
        if serializer.is_valid():
            serializer.save(current_step=2)
            return Response({'message': 'Basic details saved', 'step': 2, 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateReligionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = Profile.objects.get(user=request.user)
        serializer = ReligionSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(current_step=3)
            return Response({'message': 'Religion details saved', 'step': 3, 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateEducationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = Profile.objects.get(user=request.user)
        serializer = EducationCareerSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(current_step=4)
            return Response({'message': 'Education details saved', 'step': 4, 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateLocationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = Profile.objects.get(user=request.user)
        serializer = LocationSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(current_step=5)
            return Response({'message': 'Location saved', 'step': 5, 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdatePersonalDetailsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = Profile.objects.get(user=request.user)
        serializer = PersonalDetailsSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(is_completed=True)
            return Response({'message': 'Profile completed', 'is_completed': True, 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ==================== PROFILE GET & LIST VIEWS ====================
class AllProfilesListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profiles = Profile.objects.exclude(user=request.user).select_related('user')
        serializer = ProfileSerializer(profiles, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ProfileDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            profile = Profile.objects.select_related('user').get(id=id)

            if profile.user == request.user:
                serializer = ProfileSerializer(profile, context={"request": request})
                return Response(serializer.data, status=status.HTTP_200_OK)

            if BlockedUser.objects.filter(
                Q(user=request.user, blocked_user=profile.user) |
                Q(user=profile.user, blocked_user=request.user)
            ).exists():
                return Response(
                    {"error": "Profile not available"},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                prefs = UserPreferences.objects.get(user=profile.user)
                if prefs.profile_visibility == 'Only Me':
                    return Response(
                        {"error": "This profile is private"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                elif prefs.profile_visibility == 'Matches Only':
                    is_match = ProfileLike.objects.filter(
                        from_user=request.user, to_profile=profile
                    ).exists() and ProfileLike.objects.filter(
                        from_user=profile.user, to_profile__user=request.user
                    ).exists()
                    if not is_match:
                        return Response(
                            {"error": "Profile visible to matches only"},
                            status=status.HTTP_403_FORBIDDEN
                        )
            except UserPreferences.DoesNotExist:
                pass

            serializer = ProfileSerializer(profile, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

# ==================== PASSWORD RESET (OTP) VIEWS ====================

class SendOTPView(generics.CreateAPIView):
    serializer_class = SendOTPSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = str(random.randint(100000, 999999))
        cache.set(f'otp_{email}', otp, timeout=300)
        send_mail(
            subject='Password Reset OTP',
            message=f'Your OTP is {otp}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return Response({"message": "OTP sent successfully"})

class VerifyOTPView(generics.CreateAPIView):
    serializer_class = VerifyOTPSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp_entered = serializer.validated_data['otp']
        otp_stored = cache.get(f'otp_{email}')

        if not otp_stored:
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)

        if otp_entered != otp_stored:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        cache.set(f'otp_verified_{email}', True, timeout=600)
        cache.delete(f'otp_{email}')
        return Response({"message": "OTP verified successfully"})

class ResetPasswordView(generics.CreateAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']

        if not cache.get(f'otp_verified_{email}'):
            return Response({"error": "OTP not verified"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
            user.set_password(new_password)
            user.save()
            cache.delete(f'otp_verified_{email}')
            return Response({"message": "Password reset successful"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

# ==================== ADVERTISEMENT VIEW ====================

class AdvertisementView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_permissions(self):
        if self.request.method == 'GET' and 'admin' not in self.request.path:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, pk=None):
        if 'admin' in request.path:
            ads = Advertisement.objects.all().order_by('-created_at')
        else:
            ads = Advertisement.objects.filter(is_active=True).order_by('-created_at')

        if pk:
            try:
                ad = Advertisement.objects.get(pk=pk)
                serializer = AdvertisementSerializer(ad, context={'request': request})
                return Response(serializer.data)
            except Advertisement.DoesNotExist:
                return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdvertisementSerializer(ads, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Admin അനുമതിയില്ലാത്തവർക്ക് പരസ്യം ചേർക്കാൻ കഴിയില്ല."}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AdvertisementSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()  
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        try:
            ad = Advertisement.objects.get(pk=pk)
        except Advertisement.DoesNotExist:
            return Response({"detail": "പരസ്യം കണ്ടെത്തിയില്ല"}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff:
            return Response({"detail": "Admin അനുമതിയില്ലാത്തവർക്ക് എഡിറ്റ് ചെയ്യാൻ കഴിയില്ല."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AdvertisementSerializer(ad, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save() 
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            ad = Advertisement.objects.get(pk=pk)
        except Advertisement.DoesNotExist:
            return Response({"detail": "പരസ്യം കണ്ടെത്തിയില്ല"}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff:
            return Response({"detail": "Admin അനുമതിയില്ലാത്തവർക്ക് ഡിലീറ്റ് ചെയ്യാൻ കഴിയില്ല."}, status=status.HTTP_403_FORBIDDEN)

        ad.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
# ==================== SETTINGS PROFILE UPDATE ====================

class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        user = request.user
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            return Response({"error": "Profile Does Not Exist"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProfileSerializer(profile, context={'request': request})
        data = serializer.data
        data["email"] = user.email
        
        data["phone"] = user.phone if user.phone else (profile.phone_number if profile.phone_number else "")
        return Response(data, status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            return Response({"error": "Profile Does Not Exist"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()

        if "phone" in data:
            new_phone = data.get("phone").strip() if data.get("phone") else None
            if new_phone:
                
                if User.objects.filter(phone=new_phone).exclude(id=user.id).exists():
                    return Response({"phone": ["This phone number is already used by another account"]}, status=status.HTTP_400_BAD_REQUEST)
                user.phone = new_phone
            else:
                user.phone = None

        if "email" in data and data["email"]:
            new_email = data.get("email").strip().lower()
            if User.objects.filter(email=new_email).exclude(id=user.id).exists():
                return Response({"email": ["Email already exists"]}, status=status.HTTP_400_BAD_REQUEST)
            user.email = new_email

        user.save()

        mapped_data = {}
        mappings = {
            'full_name': 'full_name',
            'dob': 'date_of_birth',
            'location': 'district',
            'profession': 'occupation',
            'aboutMe': 'about_me',
            'motherTongue': 'mother_tongue',
            'annualIncome': 'annual_income',
            'maritalStatus': 'marital_status',
            'fatherName': 'father_name',
            'motherName': 'mother_name',
            'familyType': 'family_type',
        }

        direct_fields = ['religion', 'caste', 'education', 'company', 'country',
                        'state', 'city', 'height', 'siblings']

        for frontend_key, backend_key in mappings.items():
            if frontend_key in data:
                value = data.get(frontend_key)
                if value not in [None, '', 'null', 'undefined']:
                    mapped_data[backend_key] = value.strip() if isinstance(value, str) else value

        for field in direct_fields:
            if field in data:
                value = data.get(field)
                if value not in [None, '', 'null', 'undefined']:
                    mapped_data[field] = value.strip() if isinstance(value, str) else value

   
        if "gender" in data:
            g = data.get("gender")
            if g == "Female":
                mapped_data["gender"] = "F"
            elif g == "Male":
                mapped_data["gender"] = "M"
            elif g == "Other":
                mapped_data["gender"] = "Other"

       
        if "phone" in data:
            phone_val = data.get("phone")
            if phone_val not in [None, '', 'null', 'undefined']:
                mapped_data["phone_number"] = phone_val.strip()
            else:
                mapped_data["phone_number"] = None

        if 'profile_picture' in request.FILES:
            mapped_data['profile_picture'] = request.FILES['profile_picture']

        serializer = SettingsProfileUpdateSerializer(profile, data=mapped_data, partial=True)

        if not serializer.is_valid():
            print("Serializer Errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = serializer.save()

            gallery_files = request.FILES.getlist("gallery_images")
            for image in gallery_files:
                ProfileImage.objects.create(profile=profile, image=image)

            if profile.full_name and profile.gender and profile.date_of_birth:
                profile.is_completed = True
                profile.current_step = 5
                profile.save()

            
            updated_profile = ProfileSerializer(profile, context={'request': request}).data
            updated_profile["email"] = user.email
            updated_profile["phone"] = user.phone if user.phone else (profile.phone_number if profile.phone_number else "")
            
            return Response({
                "message": "Profile updated successfully", 
                "profile": updated_profile
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("=== UPDATE PROFILE ERROR ===")
            print(traceback.format_exc())
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# ==================== BLOCK USER ====================

class BlockUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            blocked = BlockedUser.objects.filter(user=request.user)
            serializer = BlockedUserSerializer(blocked, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print(traceback.format_exc()) 
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        blocked_user_id = request.data.get('blocked_user_id') or request.data.get('user_id')
        if not blocked_user_id:
            return Response({"error": "blocked_user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if int(blocked_user_id) == request.user.id:
            return Response({"error": "Cannot block yourself"}, status=status.HTTP_400_BAD_REQUEST)
        if BlockedUser.objects.filter(user=request.user, blocked_user_id=blocked_user_id).exists():
            return Response({"error": "Already blocked"}, status=status.HTTP_400_BAD_REQUEST)
        BlockedUser.objects.create(user=request.user, blocked_user_id=blocked_user_id)
        return Response({"message": "Blocked successfully"}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        blocked_user_id = request.data.get('blocked_user_id') or request.data.get('user_id')
        if not blocked_user_id:
            return Response({"error": "blocked_user_id or user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            blocked_user_id = int(blocked_user_id)
        except (TypeError, ValueError):
            return Response({"error": "Invalid user id"}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = BlockedUser.objects.filter(user=request.user, blocked_user_id=blocked_user_id).delete()
        if deleted:
            return Response({"message": "Unblocked successfully"}, status=status.HTTP_200_OK)
        return Response({"error": "User not found in block list"}, status=status.HTTP_404_NOT_FOUND)

# ==================== PREFERENCES ====================

class UserPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, user):
        obj, created = UserPreferences.objects.get_or_create(user=user)
        return obj

    def get(self, request):
        prefs = self.get_object(request.user)
        serializer = UserPreferencesSerializer(prefs)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        prefs = self.get_object(request.user)
        serializer = UserPreferencesSerializer(prefs, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== NOTIFICATION SETTINGS ====================

class NotificationSettingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        setting, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingSerializer(setting)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        setting, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ==================== SUBSCRIPTION ====================

class UserSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            
            sub = UserSubscription.objects.select_related('plan', 'user').get(user=request.user)
          
            if sub.expires_at and sub.expires_at < timezone.now():
                sub.deactivate()
            
            serializer = UserSubscriptionSerializer(sub)
            return Response(serializer.data)
        except UserSubscription.DoesNotExist:
            # Return default free plan
            return Response({
                'id': None,
                'plan': None,
                'plan_name': 'Free Plan',
                'price': 0,
                'features': ['limited chats', 'limited views'],
                'badge_color': '#6c757d',
                'next_billing_date': None,
                'is_active': False,
                'activated_at': None,
                'expires_at': None
            })

    def delete(self, request):
        try:
            sub = UserSubscription.objects.get(user=request.user)
            sub.deactivate()
            sub.plan = None
            sub.plan_name = "Free Plan"
            sub.price = 0
            sub.next_billing_date = None
            sub.expires_at = None
            sub.save()
            
            return Response({"message": "Subscription cancelled successfully"}, status=200)
        except UserSubscription.DoesNotExist:
            return Response({"error": "No active subscription found"}, status=404)
    
# --- Success Stories Views ---
class AdminSuccessStoryListCreateView(generics.ListCreateAPIView):
    queryset = SuccessStory.objects.all().order_by('-created_at')
    serializer_class = SuccessStorySerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] 

class AdminSuccessStoryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def put(self, request, pk):
        try:
            story = SuccessStory.objects.get(pk=pk)
        except SuccessStory.DoesNotExist:
            return Response({"error": "Success story not found"}, status=status.HTTP_404_NOT_FOUND)

        print("FILES:", request.FILES)  
        print("DATA:", request.data) 

        serializer = SuccessStorySerializer(story, data=request.data, partial=True, context={'request': request})

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        print("ERRORS:", serializer.errors) # ✅ Debug
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
# --- Subscription Plan Views ---
class AdminSubscriptionPlanListCreateView(generics.ListCreateAPIView):
    queryset = SubscriptionPlan.objects.all().order_by('price')
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        print("REQUEST DATA:", request.data)
        print("PRICE TYPE:", type(request.data.get('price')))
        return super().create(request, *args, **kwargs)

class AdminSubscriptionPlanDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def put(self, request, pk):
        try:
            plan = SubscriptionPlan.objects.get(pk=pk)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Subscription plan not found"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        serializer = SubscriptionPlanSerializer(plan, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            plan = SubscriptionPlan.objects.get(pk=pk)
            plan.delete()
            return Response({"message": "Subscription plan deleted successfully"}, status=status.HTTP_200_OK)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Subscription plan not found"}, status=status.HTTP_404_NOT_FOUND)

# --- Payments View ---
class AdminPaymentListView(generics.ListAPIView):
    queryset = Payment.objects.all().order_by('-created_at')
    serializer_class = AdminPaymentSerializer
    permission_classes = [IsAuthenticated]

class AdminPaymentDetailsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        details, created = AdminPaymentMethod.objects.get_or_create(id=1)
        return Response({
            "bank_name": details.bank_name,
            "account_number": details.account_number,
            "ifsc_code": details.ifsc_code,
            "account_holder": details.account_holder,
            "upi_id": details.upi_id,
            "qr_code": details.qr_code.url if details.qr_code else None
        })

class ProcessPlanPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id')
        transaction_id = request.data.get('transaction_id')
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            payment = Payment.objects.create(
                user=request.user,
                user_name=request.user.username,
                plan_name=plan.name,
                amount=plan.price, 
                transaction_id=transaction_id,
                status="Success"
            )
            
            sub, created = UserSubscription.objects.get_or_create(user=request.user)
            sub.activate(plan) 

            return Response({"message": "Payment verified and Plan activated!"}, status=status.HTTP_200_OK)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)

# ==================== LIKE & FAVOURITE ====================
class LikeProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id = request.data.get("profile_id")
        try:
            profile = Profile.objects.get(id=profile_id)
            like, created = ProfileLike.objects.get_or_create(
                from_user=request.user,
                to_profile=profile
            )

            if created:
                if can_send_notification(profile.user, 'like'):
                    Notification.objects.create(
                        recipient=profile.user,
                        sender=request.user,
                        notification_type='like',
                        message=f"{request.user.profile.full_name or request.user.username} liked your profile",
                        profile_id=request.user.profile.id
                    )
            return Response({"message": "liked", "created": created})
        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)


class UnlikeProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, profile_id):
        ProfileLike.objects.filter(from_user=request.user, to_profile_id=profile_id).delete()
        return Response({"message": "Like removed"}, status=status.HTTP_200_OK)


class FavouriteProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id = request.data.get("profile_id")
        try:
            profile = Profile.objects.get(id=profile_id)
            fav, created = FavouriteProfile.objects.get_or_create(
                user=request.user,
                profile=profile
            )

            if created:
                if can_send_notification(profile.user, 'favourite'):
                    Notification.objects.create(
                        recipient=profile.user,
                        sender=request.user,
                        notification_type='favourite',
                        message=f"{request.user.profile.full_name or request.user.username} added you to favourites",
                        profile_id=request.user.profile.id
                    )

                return Response({"message": "Added to favourites"}, status=status.HTTP_201_CREATED)
            return Response({"message": "Already favourite"}, status=status.HTTP_200_OK)
        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)


class RemoveFavouriteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, profile_id):
        FavouriteProfile.objects.filter(user=request.user, profile_id=profile_id).delete()
        return Response({"message": "Favourite removed"}, status=status.HTTP_200_OK)


class MyLikesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        likes = ProfileLike.objects.filter(from_user=request.user)
        profile_ids = likes.values_list("to_profile_id", flat=True)
        profiles = Profile.objects.filter(id__in=profile_ids)
        serializer = ProfileSerializer(profiles, many=True, context={"request": request})
        return Response(serializer.data)


class MyFavouriteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favourites = FavouriteProfile.objects.filter(user=request.user)
        profile_ids = favourites.values_list("profile_id", flat=True)
        profiles = Profile.objects.filter(id__in=profile_ids)
        serializer = ProfileSerializer(profiles, many=True, context={"request": request})
        return Response(serializer.data)


def can_send_notification(recipient, notification_type):
    try:
        settings = NotificationSettings.objects.get(user=recipient)
        if notification_type == 'like' and not settings.likes:
            return False
        elif notification_type == 'favourite' and not settings.favourites:
            return False
        elif notification_type == 'message' and not settings.messages:
            return False
        elif notification_type == 'profile_view' and not settings.profile_views:
            return False
        return True
    except NotificationSettings.DoesNotExist:
        return True

# ==================== NOTIFICATIONS & COMMENTS & CHAT ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_comment(request):
    profile_id = request.data.get('profile_id')
    text = request.data.get('text')

    try:
        profile = Profile.objects.get(id=profile_id)
        comment = Comment.objects.create(
            profile=profile,
            user=request.user,
            text=text
        )
        Notification.objects.create(
            recipient=profile.user,
            sender=request.user,
            notification_type='comment',
            message=f"{request.user.profile.full_name or request.user.username} commented on your profile",
            profile_id=profile_id
        )
        return Response(CommentSerializer(comment).data)
    except Profile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    notifications = Notification.objects.filter(recipient=request.user)  
    try:
        settings = NotificationSettings.objects.get(user=request.user)
        filtered_notifications = []
        
        for notif in notifications:
            if notif.notification_type == 'like' and not settings.likes:
                continue
            elif notif.notification_type == 'favourite' and not settings.favourites:
                continue
            elif notif.notification_type == 'message' and not settings.messages:
                continue
            elif notif.notification_type == 'profile_view' and not settings.profile_views:
                continue
            filtered_notifications.append(notif)
        
        serializer = NotificationSerializer(filtered_notifications[:20], many=True, context={'request': request})
        return Response(serializer.data)
        
    except NotificationSettings.DoesNotExist:
        serializer = NotificationSerializer(notifications[:20], many=True, context={'request': request})
        return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    updated = Notification.objects.filter(
        id=notification_id, 
        recipient=request.user
    ).update(is_read=True)
    
    if updated:
        return Response({'status': 'read'})
    return Response({'error': 'Notification not found'}, status=404)


class NotificationSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        setting, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(setting)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        setting, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK) # saved data thirichu ayakkam
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_rooms(request):
    blocked_users = BlockedUser.objects.filter(user=request.user).values_list('blocked_user_id', flat=True)
    blocking_me = BlockedUser.objects.filter(blocked_user=request.user).values_list('user_id', flat=True)
    all_blocked = set(list(blocked_users) + list(blocking_me))

    rooms = ChatRoom.objects.filter(
        Q(user1=request.user) | Q(user2=request.user)
    ).exclude(user1__id__in=all_blocked).exclude(user2__id__in=all_blocked).order_by('-updated_at')

    return Response(ChatRoomSerializer(rooms, many=True, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_or_get_chat(request):
    try:
        other_user_id = request.data.get("user_id")

        if not other_user_id:
            return Response({"error": "user_id required"}, status=400)

        try:
            other_user_id = int(other_user_id)
        except (ValueError, TypeError):
            return Response({"error": "Invalid user_id format"}, status=400)

        if request.user.id == other_user_id:
            return Response({"error": "You cannot chat with yourself"}, status=400)

        try:
            other_user = User.objects.get(id=other_user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        is_blocked = BlockedUser.objects.filter(
            Q(user=request.user, blocked_user_id=other_user_id) |
            Q(user_id=other_user_id, blocked_user=request.user)
        ).exists()

        if is_blocked:
            return Response({"error": "Cannot chat with a blocked user"}, status=403)

        if not request.user.is_staff and not other_user.is_staff:
            user_profile = getattr(request.user, 'profile', None)
            other_profile = getattr(other_user, 'profile', None)

            if not user_profile or not other_profile:
                return Response({'error': 'Profile incomplete'}, status=400)

            mutual = ProfileLike.objects.filter(
                from_user=request.user, to_profile=other_profile
            ).exists() and ProfileLike.objects.filter(
                from_user=other_user, to_profile=user_profile
            ).exists()

            if not mutual:
                return Response({'error': 'You can only chat with mutual matches'}, status=403)

        u1, u2 = (request.user, other_user) if request.user.id < other_user.id else (other_user, request.user)
        room, created = ChatRoom.objects.get_or_create(
            user1=u1,
            user2=u2,
            defaults={'status': 'pending', 'initiated_by': request.user}
        )

        if request.user.is_staff or other_user.is_staff:
            room.status = 'accepted'
            room.save()

        if room.status == 'rejected':
            room.status = 'pending'
            room.initiated_by = request.user
            room.save()

        elif room.status == 'pending' and room.initiated_by!= request.user:
            room.status = 'accepted'
            room.save()
            Message.objects.create(
                room=room, 
                sender=request.user,
                text="Chat request accepted. You can now send messages.",
                message_type='system'
            )

        if created and not room.messages.exists():
            Message.objects.create(
                room=room,
                sender=request.user,
                text="👋 Chat request sent",
                message_type='system'
            )

        return Response({"room_id": room.id, "status": room.status})

    except Exception as e:
        print("Error in create_or_get_chat:", str(e))
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_messages(request, room_id):
    try:
        room = ChatRoom.objects.get(Q(id=room_id) & (Q(user1=request.user) | Q(user2=request.user)))
        user = request.user
        
        messages = room.messages.filter(
            is_deleted_for_everyone=False
        ).exclude(
            deleted_by=user
        ).select_related('sender__profile').order_by('created_at')
        
        messages.exclude(sender=user).filter(is_read=False).update(is_read=True)
        
        return Response(MessageSerializer(messages, many=True, context={'request': request}).data)
    except ChatRoom.DoesNotExist:
        return Response({'error': 'Chat room not found or access denied'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    room_id = request.data.get('room_id')
    text = request.data.get('text')
    reply_to_id = request.data.get('reply_to')

    if not text or not text.strip():
        return Response({'error': 'Message text required'}, status=400)

    try:
        room = ChatRoom.objects.get(Q(id=room_id) & (Q(user1=request.user) | Q(user2=request.user)))

        if room.status == 'rejected':
            return Response({'error': 'This chat request was rejected. Cannot send message.'}, status=403)

        if room.status == 'pending' and room.initiated_by == request.user:
            return Response({'error': 'Waiting for user to accept chat request'}, status=403)

        if room.status == 'pending' and room.initiated_by!= request.user:
            room.status = 'accepted'
            room.save()

        reply_to_msg = None
        if reply_to_id:
            try:
                reply_to_msg = Message.objects.get(id=reply_to_id, room=room, is_deleted_for_everyone=False)
            except Message.DoesNotExist:
                pass

        message = Message.objects.create(
            room=room,
            sender=request.user,
            text=text.strip(),
            message_type='text',
            reply_to=reply_to_msg
        )

        room.updated_at = timezone.now()
        room.save()

        receiver = room.user2 if room.user1 == request.user else room.user1
        sender_profile = getattr(request.user, 'profile', None)
        admin_profile = getattr(request.user, 'admin_profile', None)
        sender_name = sender_profile.full_name if sender_profile and sender_profile.full_name else (admin_profile.full_name if admin_profile and admin_profile.full_name else request.user.username)

        try:
            Notification.objects.create(
                recipient=receiver, 
                sender=request.user, 
                notification_type='message', 
                message=f"{sender_name} sent you a message"
            )
        except: pass

        return Response(MessageSerializer(message, context={'request': request}).data)
    except ChatRoom.DoesNotExist:
        return Response({'error': 'Chat room not found or access denied'}, status=404)
    except Exception as e:
        print("Error in send_message:", str(e)) 
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def send_voice_message(request):
    room_id = request.data.get('room_id')
    voice_file = request.FILES.get('voice_file')
    reply_to_id = request.data.get('reply_to')
    
    if not voice_file:
        return Response({'error': 'Voice file required'}, status=400)
    try:
        room = ChatRoom.objects.get(Q(id=room_id) & (Q(user1=request.user) | Q(user2=request.user)))
        if room.status == 'rejected': return Response({'error': 'Rejected chat'}, status=403)
        if room.status == 'pending' and room.initiated_by == request.user:
            return Response({'error': 'Waiting for user to accept'}, status=403)
        
        if room.status == 'pending' and room.initiated_by!= request.user:
            room.status = 'accepted'
            room.save()

        reply_to_msg = None
        if reply_to_id:
            try:
                reply_to_msg = Message.objects.get(id=reply_to_id, room=room, is_deleted_for_everyone=False)
            except Message.DoesNotExist:
                pass

        message = Message.objects.create(
            room=room,
            sender=request.user, 
            message_type='voice',
            voice_file=voice_file,
            reply_to=reply_to_msg
        )
        
        room.updated_at = timezone.now()
        room.save()
        
        return Response(MessageSerializer(message, context={'request': request}).data)
    except ChatRoom.DoesNotExist: 
        return Response({'error': 'Chat room not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def send_image_message(request):
    room_id = request.data.get('room_id')
    image = request.FILES.get('image')
    reply_to_id = request.data.get('reply_to')
    
    if not image:
        return Response({'error': 'Image file required'}, status=400)
    try:
        room = ChatRoom.objects.get(Q(id=room_id) & (Q(user1=request.user) | Q(user2=request.user)))
        if room.status == 'rejected': return Response({'error': 'Rejected chat'}, status=403)
        if room.status == 'pending' and room.initiated_by == request.user:
            return Response({'error': 'Waiting for user to accept'}, status=403)

        if room.status == 'pending' and room.initiated_by!= request.user:
            room.status = 'accepted'
            room.save()

        reply_to_msg = None
        if reply_to_id:
            try:
                reply_to_msg = Message.objects.get(id=reply_to_id, room=room, is_deleted_for_everyone=False)
            except Message.DoesNotExist:
                pass

        message = Message.objects.create(
            room=room, # ✅ Fix
            sender=request.user, 
            message_type='image', 
            image=image,
            reply_to=reply_to_msg
        )
        
        room.updated_at = timezone.now()
        room.save()
        
        return Response(MessageSerializer(message, context={'request': request}).data)
    except ChatRoom.DoesNotExist: 
        return Response({'error': 'Chat room not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_request_action(request, room_id):
    action = request.data.get('action')
    try:
        room = ChatRoom.objects.get(id=room_id)
        if request.user not in [room.user1, room.user2]:
            return Response({'error': 'Not authorized'}, status=403)

        if room.initiated_by == request.user:
            return Response({'error': 'You cannot accept your own request'}, status=403)

        if action == 'accept':
            room.status = 'accepted'
            room.updated_at = timezone.now()
            room.save()
            
            Message.objects.create(
                room=room, # ✅ Fix
                sender=request.user,
                text="Chat request accepted. You can now send messages.",
                message_type='system'
            )
            
            return Response({"message": "Request accepted", "status": "accepted"})
        elif action == 'reject':
            room.status = 'rejected'
            room.save()
            return Response({"message": "Request rejected", "status": "rejected"})
        elif action == 'ignore':
            room.delete()
            return Response({"message": "Request ignored. User can message again.", "status": "ignored"})
        return Response({"error": "Invalid action"}, status=400)
    except ChatRoom.DoesNotExist:
        return Response({"error": "Chat room not found"}, status=404)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_messages_view(request):
    message_id = request.data.get('message_id')
    room_id = request.data.get('room_id')
    clear_all = request.data.get('clear_all', False)
    for_everyone = request.data.get('for_everyone', False)

    if clear_all and room_id:
        try:
            room = ChatRoom.objects.get(id=room_id)
            if request.user not in [room.user1, room.user2]:
                return Response({'error': 'Not authorized'}, status=403)
            messages = Message.objects.filter(room=room) 
            for m in messages:
                m.deleted_by.add(request.user)
            return Response({"message": "Chat cleared successfully"})
        except ChatRoom.DoesNotExist:
            return Response({"error": "Room not found"}, status=404)

    if message_id:
        try:
            msg = Message.objects.get(id=message_id)
            room = msg.room 
            
            if request.user not in [room.user1, room.user2]:
                return Response({'error': 'Not authorized'}, status=403)
            
            if for_everyone:
                if msg.sender!= request.user:
                    return Response({'error': 'Only sender can delete for everyone'}, status=403)
                
                msg.is_deleted_for_everyone = True
                msg.text = "This message was deleted"
                msg.image = None
                msg.voice_file = None
                msg.save()
            else:
                msg.deleted_by.add(request.user)
            
            return Response({"message": "Message deleted successfully"})
        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=404)

    return Response({"error": "Missing params"}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def block_user(request):
    serializer = BlockedUserSerializer(data=request.data, context={'request': request})

    if not serializer.is_valid():
        print("Block User Validation Error:", serializer.errors) # Debug
        return Response(serializer.errors, status=400)

    try:
        blocked_user_instance = serializer.save()
        return Response({'message': 'User blocked successfully'})
    except User.DoesNotExist:
        return Response({'error': 'User to block not found'}, status=404)
    except Exception as e:
        print("Block User Error:", str(e))
        return Response({'error': 'Failed to block user'}, status=500)

def get_or_create_admin_chat_room(user):
    
    admin_user = User.objects.filter(is_staff=True, is_superuser=True).first()
    if not admin_user:
        print("ERROR: No admin superuser found")
        return None

    u1, u2 = (user, admin_user) if user.id < admin_user.id else (admin_user, user)
    room, created = ChatRoom.objects.get_or_create(
        user1=u1, user2=u2,
        defaults={'status': 'accepted', 'initiated_by': user}
    )

    if room.status!= 'accepted':
        room.status = 'accepted'
        room.save()
    return room

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_support_message_api(request):
    try:
        subject = request.data.get("subject", "Support Issue")
        message_text = request.data.get("message")
        attachment = request.FILES.get("attachment")

        if not message_text:
            return Response({"error": "Message text is required"}, status=400)

        room = get_or_create_admin_chat_room(request.user)
        if not room:
            return Response({"error": "Admin support account not found"}, status=404)

        full_content = f"📌 [SUPPORT - {subject}]\n\n{message_text}"

        Message.objects.create(
            room=room,
            sender=request.user,
            text=full_content,
            image=attachment if attachment else None,
            message_type='text' 
        )

        return Response({"success": True, "room_id": room.id, "message": "Sent to support chat successfully!"})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_problem_api(request):
    try:
        issue_type = request.data.get("issue_type", "Bug")
        description = request.data.get("description")
        attachment = request.FILES.get("attachment")

        if not description:
            return Response({"error": "Description is required"}, status=400)

        room = get_or_create_admin_chat_room(request.user)
        if not room:
            return Response({"error": "Admin support account not found"}, status=404)

        full_content = f"⚠️ [REPORT - {issue_type}]\n\n{description}"

        Message.objects.create(
            room=room,
            sender=request.user,
            text=full_content,
            image=attachment if attachment else None,
            message_type='text' 
        )

        return Response({"success": True, "room_id": room.id, "message": "Problem reported to support chat!"})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user

    current_password = request.data.get("current_password")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not user.check_password(current_password):
        return Response({"error": "Current password is incorrect"}, status=400)

    if new_password != confirm_password:
        return Response({"error": "New password and confirm password do not match"}, status=400)

    if len(new_password) < 8:
        return Response({"error": "Password must be at least 8 characters"}, status=400)

    user.set_password(new_password)
    user.save()
    return Response({"message": "Password updated successfully"}, status=200)

# ==================== ADMIN PANEL VIEWS ====================

class AdminUsersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        users = User.objects.select_related('profile').all().order_by('-date_joined')
        serializer = AdminUserListSerializer(users, many=True, context={'request': request})
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        serializer = AdminCreateUserSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.create_user(
                username=serializer.validated_data['email'],
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                phone=serializer.validated_data.get('phone_number', '')
            )
            Profile.objects.create(
                user=user,
                full_name=serializer.validated_data['full_name'],
                phone_number=serializer.validated_data.get('phone_number', ''),
                created_by_admin=request.user,
                is_created_by_admin=True,
                is_completed=True,
                current_step=5,
                gender='M'
            )
            return Response({"message": "User created successfully", "user_id": user.id}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
class AdminUserDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, user_id):
        user = get_object_or_404(User.objects.select_related('profile'), id=user_id)
        serializer = AdminUserListSerializer(user, context={'request': request})
        profile_serializer = AdminProfileSerializer(user.profile, context={'request': request})
        return Response({
            'user': serializer.data,
            'profile': profile_serializer.data
        })

    def delete(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        if user.is_superuser:
            return Response({"error": "Cannot delete superuser"}, status=status.HTTP_403_FORBIDDEN)
        user.delete()
        return Response({"message": "User deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class AdminProfilesView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        try:
            # 1. ഫ്രണ്ട്-എൻഡിൽ നിന്നുള്ള ഫിൽട്ടർ പാരാമീറ്ററുകൾ എടുക്കുന്നു
            status_param = request.query_params.get('status', None)
            religion_param = request.query_params.get('religion', None)
            
            # 2. എല്ലാ പ്രൊഫൈലുകളും എടുക്കുന്നു (جديد ആദ്യം വരാൻ -id നൽകാം)
            profiles = Profile.objects.all().order_by('-id')
            
            # 3. സുരക്ഷിതമായി ഫിൽട്ടർ ചെയ്യുന്നു (ബ്ലാങ്ക് വാല്യൂസ് ഒഴിവാക്കാൻ)
            if status_param and status_param.strip() != "":
                profiles = profiles.filter(status__iexact=status_param.strip())
                
            if religion_param and religion_param.strip() != "":
                profiles = profiles.filter(religion__iexact=religion_param.strip())
                
            # 4. സീരിയലൈസർ വഴി ഡാറ്റ ഫ്രണ്ട്-എൻഡിലേക്ക് അയക്കുന്നു
            serializer = ProfileSerializer(profiles, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            # എറർ എന്താണെന്ന് ടെർമിനലിൽ പ്രിന്റ് ചെയ്ത് കാണാൻ
            print("Django AdminProfilesView Get Error:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
class AdminDashboardStatsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = 0
        verified_profiles = 0
        pending_profiles = 0
        rejected_profiles = 0
        match_count = 0
        recent_matches_list = []
        recent_messages_list = []
        messages_sent_count = 0
        success_stories_list = []
        total_revenue = 0

        # 1. BASIC COUNTS & SUCCESS STORIES
        try:
            total_users = User.objects.count()
            verified_profiles = Profile.objects.filter(verification_status='verified').count()
            pending_profiles = Profile.objects.filter(verification_status='pending').count()
            rejected_profiles = Profile.objects.filter(verification_status='rejected').count()
            messages_sent_count = Message.objects.count()

            stories = SuccessStory.objects.all().order_by('-created_at')
            success_stories_list = SuccessStorySerializer(stories, many=True, context={'request': request}).data
        except Exception as e:
            print("Error in basic counts:", str(e))

        # 2. SAFE IMAGE URL BUILDER
        def get_full_image_url(profile_obj):
            if profile_obj and profile_obj.profile_picture:
                try:
                    return request.build_absolute_uri(profile_obj.profile_picture.url)
                except (ValueError, AttributeError):
                    return None
            return None

        # 3. MUTUAL MATCHES LOGIC
        try:
            all_likes = ProfileLike.objects.all().select_related('from_user__profile', 'to_profile__user')
            processed_pairs = set()

            for l in all_likes:
                user_a = l.from_user
                prof_a = getattr(user_a, 'profile', None)

                prof_b = l.to_profile
                if not prof_b:
                    continue
                user_b = getattr(prof_b, 'user', None)

                if not user_a or not user_b:
                    continue

                pair = tuple(sorted([user_a.id, user_b.id]))

                if pair not in processed_pairs:
                    has_returned_like = ProfileLike.objects.filter(
                        from_user=user_b,
                        to_profile=prof_a
                    ).exists()

                    if has_returned_like:
                        match_count += 1

                        img_a = get_full_image_url(prof_a)
                        img_b = get_full_image_url(prof_b)

                        recent_matches_list.append({
                            'id': f"match_{user_a.id}_{user_b.id}",
                            'user_one_id': user_a.id,
                            'user_one_profile_id': prof_a.id if prof_a else None,
                            'user_one_name': prof_a.full_name if (prof_a and prof_a.full_name) else user_a.username,
                            'user_one_img': img_a,
                            'user_two_id': user_b.id,
                            'user_two_profile_id': prof_b.id if prof_b else None,
                            'user_two_name': prof_b.full_name if (prof_b and prof_b.full_name) else user_b.username,
                            'user_two_img': img_b,
                            'created_at': l.created_at.isoformat() if hasattr(l, 'created_at') and l.created_at else None
                        })
                    processed_pairs.add(pair)
        except Exception as match_err:
            print("Error in mutual matches logic:", str(match_err))

        # 4. RECENT MESSAGES LOGIC
        try:
            admin_rooms = ChatRoom.objects.filter(
                Q(user1=request.user) | Q(user2=request.user)
            )
            admin_messages = Message.objects.filter(
                room__in=admin_rooms
            ).exclude(
                sender=request.user
            ).select_related('sender__profile', 'room').order_by('-created_at')[:5]

            for msg in admin_messages:
                sender_prof = getattr(msg.sender, 'profile', None)
                msg_img = get_full_image_url(sender_prof)
                msg_text = msg.text or ""
                msg_type = 'normal'
                if msg_text.startswith('⚠️ [REPORT'):
                    msg_type = 'report'
                elif msg_text.startswith('📌 [SUPPORT'):
                    msg_type = 'support'
                elif msg_text.startswith('📞 [CONTACT'):
                    msg_type = 'contact'
                display_text = msg_text[:100] if msg_text else "Sent a message"

                recent_messages_list.append({
                    'id': msg.id,
                    'sender_name': sender_prof.full_name if (sender_prof and sender_prof.full_name) else msg.sender.username,
                    'sender_image': msg_img,
                    'message_text': display_text,
                    'timestamp': msg.created_at.isoformat() if msg.created_at else None,
                    'room_id': msg.room.id,
                    'message_type': msg_type
                })
        except Exception as msg_err:
            print("Error in recent messages logic:", str(msg_err))

        # 5. REVENUE CALCULATION 
        try:
            revenue_data = Payment.objects.filter(
                Q(status='Success') | Q(status='completed')
            ).aggregate(Sum('amount'))
            total_revenue = revenue_data['amount__sum'] if revenue_data['amount__sum'] else 0
        except Exception as rev_err:
            print("Error in revenue logic:", str(rev_err))

        user_growth_labels = []
        user_growth_data = []

        try:
            today = timezone.now().date()
            month_start = today.replace(day=1)
            current_date = month_start

            while current_date <= today:
                total_users_till_date = User.objects.filter(
                    date_joined__date__lte=current_date
                ).count()

                user_growth_labels.append(current_date.strftime("%d %b"))
                user_growth_data.append(total_users_till_date)
                current_date += timedelta(days=7)

            if user_growth_labels[-1]!= today.strftime("%d %b"):
                user_growth_labels.append(today.strftime("%d %b"))
                user_growth_data.append(
                    User.objects.filter(date_joined__date__lte=today).count()
                )

        except Exception as e:
            print("Growth Error:", e)

        # 7. RESPONSE DATA
        data = {
            'total_users': total_users,
            'active_matches': match_count,
            'messages_sent': messages_sent_count,
            'verified_profiles': verified_profiles,
            'pending_profiles': pending_profiles,
            'rejected_profiles': rejected_profiles,
            'recent_matches': recent_matches_list[:5],
            'recent_messages': recent_messages_list,
            'success_stories': success_stories_list,
            'revenue': int(total_revenue), 
            'user_growth_labels': user_growth_labels,
            'user_growth_data': user_growth_data,
        }

        return Response(data)



class AdminVerifyProfileView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, profile_id):
        try:
            profile = Profile.objects.select_related('user').get(id=profile_id)
            status_val = request.data.get('status')

            if status_val == 'verified':
                try:
                    aadhaar = AadhaarVerification.objects.get(user=profile.user)
                except AadhaarVerification.DoesNotExist:
                    return Response({"error": "Aadhaar not uploaded. Cannot verify."}, status=status.HTTP_400_BAD_REQUEST)

                profile.verification_status = 'verified'
                profile.rejection_reason = ''
                profile.verified_by = request.user
                profile.verified_at = timezone.now()
                profile.save()

                aadhaar.status = 'verified'
                aadhaar.verified_at = timezone.now()
                aadhaar.verified_by = request.user
                aadhaar.save()

            elif status_val == 'rejected':
                rejection_reason = request.data.get('rejection_reason', '').strip()
                if not rejection_reason:
                    return Response({"error": "Rejection reason required"}, status=400)

                profile.verification_status = 'rejected'
                profile.rejection_reason = rejection_reason
                profile.verified_by = None
                profile.verified_at = None
                profile.save()

                AadhaarVerification.objects.filter(user=profile.user).update(
                    status='rejected',
                    rejection_reason=rejection_reason
                )

            elif status_val == 'pending':
                profile.verification_status = 'pending'
                profile.rejection_reason = ''
                profile.verified_by = None
                profile.verified_at = None
                profile.save()

                AadhaarVerification.objects.filter(user=profile.user).update(
                    status='pending',
                    rejection_reason=''
                )
            else:
                return Response({"error": "Invalid status"}, status=400)

            return Response({"message": f"Profile {status_val} successfully"})

        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
class AdminRecentRegistrationsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        recent_users = User.objects.select_related('profile').order_by('-date_joined')[:10]
        serializer = AdminUserListSerializer(recent_users, many=True, context={'request': request})
        return Response(serializer.data)


class AdminProfileListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminProfileListSerializer
    
    def get_queryset(self):
        queryset = Profile.objects.select_related('user').all()
        status = self.request.query_params.get('status', None)
        religion = self.request.query_params.get('religion', None)
        
        if status and status != 'all':
            queryset = queryset.filter(verification_status=status.lower())
        if religion and religion != 'all':
            queryset = queryset.filter(religion=religion)
            
        return queryset.order_by('-created_at')

    def get_serializer_context(self):
        return {'request': self.request}


class AadhaarVerificationView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        try:
            aadhaar = request.user.aadhaar_verification
            return Response({
                'aadhaar_number': aadhaar.aadhaar_number,
                'status': aadhaar.status,
                'rejection_reason': aadhaar.rejection_reason,
                'aadhaar_image': request.build_absolute_uri(aadhaar.aadhaar_image.url) if aadhaar.aadhaar_image else None,
                'updated_at': aadhaar.updated_at,
            })
        except AadhaarVerification.DoesNotExist:
            return Response({'status': 'not_uploaded'})

    def post(self, request):
        aadhaar_number = request.data.get('aadhaar_number')
        aadhaar_image = request.FILES.get('aadhaar_image')

        if not aadhaar_number or not aadhaar_image:
            return Response({'error': 'Aadhaar number and image required'}, status=400)

        if len(aadhaar_number) != 12 or not aadhaar_number.isdigit():
            return Response({'error': 'Aadhaar must be 12 digits'}, status=400)

        aadhaar, created = AadhaarVerification.objects.update_or_create(
            user=request.user,
            defaults={
                'aadhaar_number': aadhaar_number,
                'aadhaar_image': aadhaar_image,
                'status': 'pending',
                'rejection_reason': '',
                'verified_at': None,
                'verified_by': None,
            }
        )

        profile = request.user.profile
        if profile.verification_status == 'verified':
            profile.verification_status = 'pending'
            profile.save()

        return Response({
            'message': 'Aadhaar uploaded successfully' if created else 'Aadhaar updated successfully',
            'status': aadhaar.status
        })


class MyMatchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_profile = request.user.profile
        likes = ProfileLike.objects.filter(
            from_user=request.user
        ).select_related("to_profile", "to_profile__user")

        data = []
        for like in likes:
            other_profile = like.to_profile
            mutual = ProfileLike.objects.filter(
                from_user=other_profile.user,
                to_profile=user_profile
            ).exists()

            if mutual:
                age = None
                if other_profile.date_of_birth:
                    today = date.today()
                    age = today.year - other_profile.date_of_birth.year - ((today.month, today.day) < (other_profile.date_of_birth.month, other_profile.date_of_birth.day))

                data.append({
                    "id": other_profile.id,
                    "user_id": other_profile.user.id,
                    "full_name": other_profile.full_name,
                    "age": age,
                    "religion": other_profile.religion,
                    "occupation": other_profile.occupation,
                    "education": other_profile.education,
                    "district": other_profile.district,
                    "city": other_profile.city,
                    "profile_picture": request.build_absolute_uri(
                        other_profile.profile_picture.url
                    ) if other_profile.profile_picture else None,
                    "is_verified": getattr(other_profile, 'is_verified', False), 
                    "is_premium": getattr(other_profile, 'is_premium', False), 
                })

        return Response(data)

class PublicProfileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        prefs, _ = UserPreferences.objects.get_or_create(user=user)
        profiles = Profile.objects.filter(user__is_staff=False).exclude(user=user).select_related('user')

        if prefs.show_me == 'Men':
            profiles = profiles.filter(gender='M')
        elif prefs.show_me == 'Women':
            profiles = profiles.filter(gender='F')

        today = date.today()
        age_ranges = {
            '18 - 25': (18, 25),
            '22 - 30': (22, 30),
            '25 - 35': (25, 35),
            '30 - 40': (30, 40),
            '40+': (40, 100)
        }
        if prefs.age_preference in age_ranges:
            min_age, max_age = age_ranges[prefs.age_preference]
            max_date = today - timedelta(days=min_age * 365)
            min_date = today - timedelta(days=max_age * 365)
            profiles = profiles.filter(date_of_birth__lte=max_date, date_of_birth__gte=min_date)
      
        blocked_users = BlockedUser.objects.filter(user=user).values_list('blocked_user_id', flat=True)
        blocked_by_users = BlockedUser.objects.filter(blocked_user=user).values_list('user_id', flat=True)
        profiles = profiles.exclude(user_id__in=blocked_users).exclude(user_id__in=blocked_by_users)

        serializer = ProfileSerializer(profiles, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        user = request.user
        admin_profile, created = AdminProfile.objects.get_or_create(
            user=user,
            defaults={
                'full_name': user.get_full_name() or user.username,
                'role': 'Super Admin' if user.is_superuser else 'Admin'
            }
        )
        serializer = AdminProfileDetailSerializer(admin_profile, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        user = request.user
        admin_profile, created = AdminProfile.objects.get_or_create(user=user)
        data = request.data.copy()

        # Gender validation & cleaning
        if 'gender' in data:
            gender_val = data.get('gender')
            if gender_val:
                gender_val = str(gender_val).strip().replace('"', '').replace("'", "").title()
                if gender_val in ['Male', 'Female']:
                    data['gender'] = gender_val
                else:
                    data['gender'] = None
            else:
                data['gender'] = None

        # Cleaning Nullable fields
        if 'date_of_birth' in data:
            dob_val = str(data.get('date_of_birth')).strip().replace('"', '').replace("'", "")
            if dob_val in ['', 'null', 'None', 'undefined']:
                data['date_of_birth'] = None

        if 'phone' in data:
            phone_val = str(data.get('phone')).strip().replace('"', '').replace("'", "")
            if phone_val in ['', 'null', 'None', 'undefined']:
                data['phone'] = None

        serializer = AdminProfileDetailSerializer(
            admin_profile,
            data=data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            instance = serializer.save()
            instance.refresh_from_db()
            response_serializer = AdminProfileDetailSerializer(instance, context={'request': request})
            return Response({
                "message": "Profile updated successfully",
                "profile": response_serializer.data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== 2. CHANGE PASSWORD VIEW (PUT METHOD) ====================
@api_view(["PUT"]) # 🔄 405 എറർ വരാതിരിക്കാൻ PUT മെത്തേഡ് കൃത്യമായി സെറ്റ് ചെയ്തു
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    # ഫ്രണ്ട് എൻഡിൽ നിന്ന് വരാവുന്ന 'old_password' അല്ലെങ്കിൽ 'current_password' ചെക്ക് ചെയ്യുന്നു
    old_password = request.data.get("old_password") or request.data.get("current_password")
    new_password = request.data.get("new_password")

    if not old_password or not new_password:
        return Response({"error": "Both current password and new password are required."}, status=status.HTTP_400_BAD_REQUEST)

    # നിലവിലെ പാസ്‌വേഡ് ശരിയാണോ എന്ന് പരിശോധിക്കുന്നു
    if not user.check_password(old_password):
        return Response({"error": "Incorrect current password."}, status=status.HTTP_400_BAD_REQUEST)

    # പുതിയ പാസ്‌വേഡ് സെറ്റ് ചെയ്യുന്നു
    user.set_password(new_password)
    user.save()
    
    return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)


# ==================== 3. GET ADMIN USER ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_admin_user(request):
    admin = User.objects.filter(is_staff=True).first()
    if not admin:
        return Response({"error": "Admin not found"}, status=404)
    return Response({"id": admin.id, "username": admin.username})

# --- Success Stories Views ---
class AdminSuccessStoryListCreateView(generics.ListCreateAPIView):
    queryset = SuccessStory.objects.all().order_by('-created_at')
    serializer_class = SuccessStorySerializer
    permission_classes = [IsAuthenticated]

class AdminSuccessStoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SuccessStory.objects.all()
    serializer_class = SuccessStorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

# --- Subscription Plan Views ---
class AdminSubscriptionPlanView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        plans = SubscriptionPlan.objects.all().order_by('-id')
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data.copy()
        
        if 'price' in data and not str(data['price']).startswith('₹'):
            data['price'] = f"₹{data['price']}"

        serializer = SubscriptionPlanSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- Payments View ---
class AdminPaymentListView(generics.ListAPIView):
    queryset = Payment.objects.all().order_by('-created_at') 
    serializer_class = AdminPaymentSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user_name', 'plan_name', 'transaction_id']
    ordering_fields = ['created_at', 'amount']
    

class AdminUserGrowthView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=29)
        users_by_date = User.objects.filter(
            date_joined__date__range=[start_date, end_date]
        ).annotate(
            date=TruncDate('date_joined')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')

        # Fill missing dates with 0
        date_dict = {item['date']: item['count'] for item in users_by_date}
        labels = []
        data = []
        
        for i in range(30):
            current_date = start_date + timedelta(days=i)
            labels.append(current_date.strftime('%b %d')) # Jan 01
            data.append(date_dict.get(current_date, 0))
        
        return Response({
            'labels': labels,
            'data': data,
            'total': User.objects.count()
        })
class CreateRazorpayOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id')
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            amount = int(plan.price * 100) 

            razorpay_order = razorpay_client.order.create({
                "amount": amount,
                "currency": "INR",
                "receipt": f"plan_{plan.id}_user_{request.user.id}",
                "notes": {
                    "plan_id": str(plan.id),
                    "user_id": str(request.user.id),
                    "plan_name": plan.name
                }
            })

            return Response({
                "order_id": razorpay_order['id'],
                "amount": amount,
                "currency": "INR",
                "key": settings.RAZORPAY_KEY_ID,
                "plan_name": plan.name,
                "plan_id": plan.id
            }, status=status.HTTP_200_OK)

        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Plan not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')
        plan_id = request.data.get('plan_id')

        try:
            # 1. Verify Signature
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            client.utility.verify_payment_signature(params_dict)
            plan = SubscriptionPlan.objects.get(id=plan_id)
            existing_sub = UserSubscription.objects.filter(
                user=request.user,
                is_active=True
            ).first()

            if existing_sub:
                existing_sub.is_active = False
                existing_sub.cancelled_at = timezone.now() 
                existing_sub.save()
            sub, created = UserSubscription.objects.get_or_create(user=request.user)
            sub.activate(plan) 

            Payment.objects.create(
                user=request.user,
                user_name=request.user.username,
                plan_name=plan.name,
                amount=plan.price,
                transaction_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                status="completed"
            )
            return Response({
                "message": "Payment verified and Plan activated!",
                "plan_name": plan.name,
                "expires_at": sub.expires_at,
                "is_active": sub.is_active
            }, status=200)

        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Payment verification failed"}, status=400)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Plan not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


def get_is_verified(self, obj):
    has_payment = Payment.objects.filter(
        user=obj.user,
        status__in=['completed', 'success']
    ).exists()
    
    premium_active = False
    try:
        if hasattr(obj.user, 'subscription'):
            sub = obj.user.subscription
            premium_active = sub.is_active and sub.expires_at and sub.expires_at > timezone.now()
    except:
        pass
    return has_payment or premium_active


@api_view(['GET'])
@permission_classes([AllowAny])
def get_public_plans(request):
    try:
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data)
    except Exception as e:
        print(f"Plans API Error: {str(e)}")
        import traceback
        traceback.print_exc() 
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_success_stories_public(request):
    stories = SuccessStory.objects.all().order_by('-created_at')
    serializer = SuccessStorySerializer(stories, many=True, context={'request': request})
    return Response(serializer.data)