import os
import datetime
import re
from django.utils import timezone
from datetime import date

from datetime import date
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import InvalidToken

from .models import (
    AdminProfile, NotificationSettings, Profile, Advertisement, ProfileImage, 
    BlockedUser, UserPreferences, SupportMessage,  
    UserSubscription, ReportedProblem, ProfileLike, FavouriteProfile, 
    Notification, Comment, Message, ChatRoom, AadhaarVerification,SuccessStory, SubscriptionPlan, Payment
)

User = get_user_model()

# ==================== AUTH & REGISTER SERIALIZERS ====================

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    referral_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=True, max_length=15) 

    class Meta:
        model = User
        fields = ['name', 'email', 'password', 'confirm_password', 'phone', 'referral_id']

    def validate_email(self, value):
        email_lower = value.lower()
        if User.objects.filter(email__iexact=email_lower).exists():
            raise serializers.ValidationError("Email already registered")
        return email_lower

    def validate_phone(self, value):
        
        if not value.isdigit():
            raise serializers.ValidationError("Phone number must contain only digits")
        if len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits")
        return value

    def validate(self, attrs):
        if attrs['password']!= attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        referral_id = validated_data.pop('referral_id', None)
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            name=validated_data['name'],
            password=validated_data['password'],
            phone=validated_data['phone'], 
            referral_id=referral_id if referral_id else None
        )
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        print("ATTRS:", attrs)

        try:
            data = super().validate(attrs)
            print("SUCCESS")
        except Exception as e:
            print("ERROR:", repr(e))
            raise

        data["role"] = "admin" if self.user.is_superuser else "user"
        return data

class UpdateProfileTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['profile_type']


# ==================== CORE PROFILE SERIALIZER ====================

class ProfileSerializer(serializers.ModelSerializer):
    gallery_images = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    has_aadhaar = serializers.SerializerMethodField()
    aadhaar_status = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    is_premium = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = '__all__'

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        if request.user.is_staff or request.user.is_superuser or obj.user == request.user:
            if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
                return request.build_absolute_uri(obj.profile_picture.url)
            return None

        try:
            prefs = UserPreferences.objects.get(user=obj.user)
            if prefs.photo_visibility == 'Only Me':
                return None
            elif prefs.photo_visibility == 'Matches Only':
                is_match = ProfileLike.objects.filter(
                    from_user=request.user, to_profile=obj
                ).exists() and ProfileLike.objects.filter(
                    from_user=obj.user, to_profile__user=request.user
                ).exists()
                if not is_match:
                    return None
        except UserPreferences.DoesNotExist:
            pass

        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            return request.build_absolute_uri(obj.profile_picture.url)
        return None

    def get_gallery_images(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []

       
        if request.user.is_staff or request.user.is_superuser or obj.user == request.user:
            images = ProfileImage.objects.filter(profile=obj)
            return [{
                'id': img.id,
                'image': request.build_absolute_uri(img.image.url)
            } for img in images]

        try:
            prefs = UserPreferences.objects.get(user=obj.user)
            if prefs.photo_visibility == 'Only Me':
                return []
            elif prefs.photo_visibility == 'Matches Only':
                is_match = ProfileLike.objects.filter(
                    from_user=request.user, to_profile=obj
                ).exists() and ProfileLike.objects.filter(
                    from_user=obj.user, to_profile__user=request.user
                ).exists()
                if not is_match:
                    return []
        except UserPreferences.DoesNotExist:
            pass

        images = ProfileImage.objects.filter(profile=obj)
        return [{
            'id': img.id,
            'image': request.build_absolute_uri(img.image.url)
        } for img in images]

    def get_age(self, obj):
        if obj.date_of_birth:
            today = date.today()
            return today.year - obj.date_of_birth.year - ((today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day))
        return None

    def get_email(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        if request.user.is_staff or request.user.is_superuser or obj.user == request.user:
            return obj.user.email if obj.user else None

        try:
            prefs = UserPreferences.objects.get(user=obj.user)
            if prefs.contact_visibility == 'Only Me':
                return None
            elif prefs.contact_visibility == 'Matches Only':
                is_match = ProfileLike.objects.filter(
                    from_user=request.user, to_profile=obj
                ).exists() and ProfileLike.objects.filter(
                    from_user=obj.user, to_profile__user=request.user
                ).exists()
                if not is_match:
                    return None
        except UserPreferences.DoesNotExist:
            pass

        return obj.user.email if obj.user else None

    def get_phone(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        if request.user.is_staff or request.user.is_superuser or obj.user == request.user:
            if obj.phone_number:
                return obj.phone_number
            return obj.user.phone if obj.user and obj.user.phone else None

        try:
            prefs = UserPreferences.objects.get(user=obj.user)
            if prefs.contact_visibility == 'Only Me':
                return None
            elif prefs.contact_visibility == 'Matches Only':
                is_match = ProfileLike.objects.filter(
                    from_user=request.user, to_profile=obj
                ).exists() and ProfileLike.objects.filter(
                    from_user=obj.user, to_profile__user=request.user
                ).exists()
                if not is_match:
                    return None
        except UserPreferences.DoesNotExist:
            pass

        if obj.phone_number:
            return obj.phone_number
        return obj.user.phone if obj.user and obj.user.phone else None

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'email': obj.user.email,
            'username': obj.user.username
        } if obj.user else None

    def get_has_aadhaar(self, obj):
        if obj.user:
            return AadhaarVerification.objects.filter(user=obj.user).exists()
        return False

    def get_aadhaar_status(self, obj):
        if obj.user:
            try:
                verification = AadhaarVerification.objects.get(user=obj.user)
                return verification.status
            except AadhaarVerification.DoesNotExist:
                return None
        return None

    def get_is_premium(self, obj):
        """Check if user has active paid plan"""
        try:
            if hasattr(obj.user, 'subscription'):
                sub = obj.user.subscription
                if sub.is_active and sub.expires_at:
                    return sub.expires_at > timezone.now()
            return False
        except Exception as e:
            print(f"Error in get_is_premium: {e}")
            return False

    def get_is_verified(self, obj):
        """✅ FIXED: Payment success OR Premium active"""
        aadhar_verified = obj.verification_status == 'verified'
        
        has_payment = Payment.objects.filter(
            user=obj.user,
            status__in=['completed', 'success']
        ).exists()
        
        premium_active = False
        try:
            if hasattr(obj.user, 'subscription'):
                sub = obj.user.subscription
                premium_active = sub.is_active and sub.expires_at and sub.expires_at > timezone.now()
        except Exception as e:
            print(f"ERROR in subscription check: {e}")
        
        print(f"DEBUG {obj.full_name}: Aadhar={aadhar_verified}, Payment={has_payment}, Premium={premium_active}")
        
        return has_payment or premium_active or aadhar_verified


# ==================== MULTI-STEP CREATION SERIALIZERS ====================

class BasicDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['relation_type', 'child_type', 'child_name', 'full_name', 'gender', 'date_of_birth', 'height', 'marital_status', 'profile_picture']


class ReligionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['religion', 'caste', 'mother_tongue']


class EducationCareerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['education', 'occupation', 'company', 'annual_income']

    def validate(self, attrs):
        if 'annual_income' not in attrs:
            attrs['annual_income'] = '20000 - 100000'
        return attrs


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['country', 'state', 'district', 'city']


class PersonalDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['father_name', 'mother_name', 'family_type', 'siblings', 'about_me', 'interests']


# ==================== PASSWORD RESET (OTP) SERIALIZERS ====================

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        email_lower = value.lower()
        if not User.objects.filter(email__iexact=email_lower).exists():
            raise serializers.ValidationError("Email not registered")
        return email_lower


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value):
        return value.lower()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        return value.lower()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                "password": "Passwords don't match"
            })
        return attrs


# ==================== ADVERTISEMENT SERIALIZER ====================

class AdvertisementSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Advertisement
        fields = ['id', 'title', 'file', 'file_url', 'file_type', 'link_url', 'is_active', 'created_at']
        read_only_fields = ['file_url', 'file_type'] 

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        elif obj.file:
            return obj.file.url
        return None

# ==================== PROFILE UPDATE (SETTINGS) SERIALIZER ====================

class SettingsProfileUpdateSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = [
            'full_name', 'gender', 'date_of_birth', 'height', 'marital_status',
            'profile_picture', 'phone_number', 'religion', 'caste', 'mother_tongue',
            'education', 'occupation', 'company', 'annual_income', 'country',
            'state', 'district', 'city', 'father_name', 'mother_name',
            'family_type', 'siblings', 'about_me'
        ]
        extra_kwargs = {
            'full_name': {'required': False, 'allow_blank': True, 'allow_null': True},
            'gender': {'required': False, 'allow_null': True},
            'date_of_birth': {'required': False, 'allow_null': True},
            'height': {'required': False, 'allow_blank': True, 'allow_null': True},
            'marital_status': {'required': False, 'allow_blank': True, 'allow_null': True},
            'phone_number': {'required': False, 'allow_blank': True, 'allow_null': True},
            'religion': {'required': False, 'allow_blank': True, 'allow_null': True},
            'caste': {'required': False, 'allow_blank': True, 'allow_null': True},
            'mother_tongue': {'required': False, 'allow_blank': True, 'allow_null': True},
            'education': {'required': False, 'allow_blank': True, 'allow_null': True},
            'occupation': {'required': False, 'allow_blank': True, 'allow_null': True},
            'company': {'required': False, 'allow_blank': True, 'allow_null': True},
            'annual_income': {'required': False, 'allow_blank': True, 'allow_null': True},
            'country': {'required': False, 'allow_blank': True, 'allow_null': True},
            'state': {'required': False, 'allow_blank': True, 'allow_null': True},
            'district': {'required': False, 'allow_blank': True, 'allow_null': True},
            'city': {'required': False, 'allow_blank': True, 'allow_null': True},
            'father_name': {'required': False, 'allow_blank': True, 'allow_null': True},
            'mother_name': {'required': False, 'allow_blank': True, 'allow_null': True},
            'family_type': {'required': False, 'allow_blank': True, 'allow_null': True},
            'siblings': {'required': False, 'allow_blank': True, 'allow_null': True},
            'about_me': {'required': False, 'allow_blank': True, 'allow_null': True},
            'profile_picture': {'required': False, 'allow_null': True},
        }

    def to_internal_value(self, data):
     
        ret = super().to_internal_value(data)

        for field_name in list(ret.keys()):
            if field_name == 'profile_picture':
                continue
            value = ret[field_name]
            if value in ['', 'null', 'None', 'undefined']:
                ret[field_name] = None
            elif isinstance(value, str):
                ret[field_name] = value.strip() or None

        return ret

    def update(self, instance, validated_data):
        if 'profile_picture' in validated_data:
            if validated_data['profile_picture'] is None:
                if instance.profile_picture:
                    instance.profile_picture.delete(save=False)
                instance.profile_picture = None
            else:
                instance.profile_picture = validated_data['profile_picture']
            validated_data.pop('profile_picture')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    
# ==================== MISC FEATURES SERIALIZERS ====================

class BlockedUserSerializer(serializers.ModelSerializer):
   
    blocked_user_id = serializers.IntegerField(read_only=True)
    name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at', format="%Y-%m-%d", read_only=True)

    class Meta:
        model = BlockedUser
        fields = ['id', 'blocked_user_id', 'name', 'image', 'date']
        read_only_fields = ['user', 'created_at']

    def get_name(self, obj):
        try:
            if obj.blocked_user:
                return obj.blocked_user.get_full_name() or obj.blocked_user.username
        except:
            pass
        return "Deleted User"

    def get_image(self, obj):
        try:
            request = self.context.get('request')
            if obj.blocked_user and obj.blocked_user.profile_picture:
                if request:
                    return request.build_absolute_uri(obj.blocked_user.profile_picture.url)
                return obj.blocked_user.profile_picture.url
        except:
            pass
        return "https://via.placeholder.com/50"

    def create(self, validated_data):
        user = self.context['request'].user
        blocked_user_id = self.initial_data.get('blocked_user_id')
        if not blocked_user_id:
            raise serializers.ValidationError({"blocked_user_id": "Required"})
        if user.id == int(blocked_user_id):
            raise serializers.ValidationError({"error": "Cannot block yourself"})
        if BlockedUser.objects.filter(user=user, blocked_user_id=blocked_user_id).exists():
            raise serializers.ValidationError({"error": "Already blocked"})
        validated_data['user'] = user
        validated_data['blocked_user_id'] = blocked_user_id
        return super().create(validated_data)


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        exclude = ['user']


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ['id', 'subject', 'message', 'attachment', 'created_at']


class NotificationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        exclude = ['user']

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    badge_color = serializers.SerializerMethodField()
    plan_id = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'plan_id', 'plan_name', 'price', 'features', 'badge_color',
            'next_billing_date', 'is_active', 'activated_at', 'expires_at'
        ]

    def get_plan_name(self, obj):
        return obj.plan.name if obj.plan else 'Free Plan'

    def get_price(self, obj):
        return obj.plan.price if obj.plan else 0

    def get_features(self, obj):
        return obj.plan.features if obj.plan else ['limited chats', 'limited views']

    def get_badge_color(self, obj):
        return obj.plan.badge_color if obj.plan else '#6c757d'

    def get_plan_id(self, obj):
        return obj.plan.id if obj.plan else None

class ReportedProblemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportedProblem
        fields = ['id', 'issue_type', 'description', 'attachment', 'created_at']
        

class ProfileLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileLike
        fields = "__all__"
        read_only_fields = ["from_user", "created_at"]


class FavouriteProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavouriteProfile
        fields = "__all__"
        read_only_fields = ["user", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_image = serializers.SerializerMethodField()
    sender_profile_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'message', 'is_read', 
            'created_at', 'profile_id', 'sender_name', 
            'sender_image', 'sender_profile_id'
        ]
    
    def get_sender_name(self, obj):
        try:
            return obj.sender.profile.full_name
        except:
            return obj.sender.username
    
    def get_sender_image(self, obj):
        try:
            if obj.sender.profile.profile_picture:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.sender.profile.profile_picture.url)
                return obj.sender.profile.profile_picture.url
        except:
            pass
        return None
    
    def get_sender_profile_id(self, obj):
        try:
            return obj.sender.profile.id
        except:
            return None


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = [
            'messages', 'favourites', 'profile_views', 
            'likes', 'updates_news', 'email_notifications'
        ]


class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.profile.full_name', read_only=True)
    user_image = serializers.CharField(source='user.profile.profile_picture', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'text', 'created_at', 'user_name', 'user_image']


class ChatRoomSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_admin_chat = serializers.SerializerMethodField()
    last_message_type = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ['id', 'other_user', 'last_message', 'unread_count', 'status', 'initiated_by', 'is_admin_chat', 'last_message_type']

    def get_other_user(self, obj):
        request = self.context.get('request')
        user = request.user
        other = obj.user2 if obj.user1 == user else obj.user1
        
        image_url = None
        profile = getattr(other, 'profile', None)
        admin_profile = getattr(other, 'admin_profile', None)
        
        if profile and getattr(profile, 'profile_picture', None):
            image_url = profile.profile_picture.url
        elif admin_profile and hasattr(admin_profile, 'profile_picture') and admin_profile.profile_picture:
            image_url = admin_profile.profile_picture.url
           
        if image_url and request:
            image_url = request.build_absolute_uri(image_url)
        
        first_name = other.first_name or ""
        last_name = other.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        if profile and getattr(profile, 'full_name', None):
            full_name = profile.full_name
        elif admin_profile and hasattr(admin_profile, 'full_name') and admin_profile.full_name:
            full_name = admin_profile.full_name
        
        if not full_name:
            full_name = other.username
            
        return {
            'id': other.id,
            'first_name': first_name,
            'last_name': last_name,
            'full_name': full_name,
            'name': full_name,
            'username': other.username,
            'image': image_url,
            'is_admin': other.is_staff or other.is_superuser
        }

    def get_last_message(self, obj):
        msg = obj.messages.filter(is_deleted_for_everyone=False).order_by('-created_at').first()
        if not msg: return None
        return {
            'text': msg.text,
            'message_type': msg.message_type,
            'created_at': msg.created_at
        }

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.messages.filter(
            is_read=False,
            is_deleted_for_everyone=False
        ).exclude(
            sender=user
        ).exclude(
            deleted_by=user
        ).count()

    def get_is_admin_chat(self, obj):
        return obj.user1.is_staff or obj.user2.is_staff

    def get_last_message_type(self, obj):
        msg = obj.messages.filter(is_deleted_for_everyone=False).order_by('-created_at').first()
        if not msg: return 'normal'
        if msg.text and msg.text.startswith('⚠️ [REPORT'):
            return 'report'
        elif msg.text and msg.text.startswith('📌 [SUPPORT'):
            return 'support'
        return 'normal'


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_full_name = serializers.SerializerMethodField()
    voice_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    reply_to_text = serializers.SerializerMethodField()
    reply_to_sender_name = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField() 
    is_me = serializers.SerializerMethodField() 

    class Meta:
        model = Message
        fields = ['id', 'text', 'message_type', 'voice_url', 'image_url',
                  'is_read', 'created_at', 'sender_name', 'sender_full_name', 'sender',
                  'reply_to', 'reply_to_text', 'reply_to_sender_name', 'is_deleted_for_everyone',
                  'is_admin', 'is_me'] 

    def get_sender_name(self, obj):
        profile = getattr(obj.sender, 'profile', None)
        admin_profile = getattr(obj.sender, 'admin_profile', None)
        if profile and profile.full_name:
            return profile.full_name
        if admin_profile and admin_profile.full_name:
            return admin_profile.full_name
        if obj.sender.first_name or obj.sender.last_name:
            return f"{obj.sender.first_name} {obj.sender.last_name}".strip()
        return obj.sender.username

    def get_sender_full_name(self, obj):
        return self.get_sender_name(obj)

    def get_voice_url(self, obj):
        if obj.voice_file and not obj.is_deleted_for_everyone:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.voice_file.url) if request else obj.voice_file.url
        return None

    def get_image_url(self, obj):
        if obj.image and not obj.is_deleted_for_everyone:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_reply_to_text(self, obj):
        if obj.reply_to and not obj.reply_to.is_deleted_for_everyone:
            return obj.reply_to.text
        return "Message deleted" if obj.reply_to else None

    def get_reply_to_sender_name(self, obj):
        if obj.reply_to:
            profile = getattr(obj.reply_to.sender, 'profile', None)
            admin_profile = getattr(obj.reply_to.sender, 'admin_profile', None)
            if profile and profile.full_name:
                return profile.full_name
            if admin_profile and admin_profile.full_name:
                return admin_profile.full_name
            if obj.reply_to.sender.first_name or obj.reply_to.sender.last_name:
                return f"{obj.reply_to.sender.first_name} {obj.reply_to.sender.last_name}".strip()
            return obj.reply_to.sender.username
        return None

    def get_is_admin(self, obj): 
        return obj.sender.is_staff or obj.sender.is_superuser

    def get_is_me(self, obj): 
        request = self.context.get('request')
        return obj.sender.id == request.user.id

# ==================== ADMIN PANEL SERIALIZERS ====================

class AdminCreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, write_only=True)
    full_name = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value


class AdminUserListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='profile.full_name', read_only=True, default='')
    profile_picture = serializers.ImageField(source='profile.profile_picture', read_only=True)
    role = serializers.SerializerMethodField()
    created_by_admin = serializers.CharField(source='profile.created_by_admin.username', read_only=True, default=None)
    is_created_by_admin = serializers.BooleanField(source='profile.is_created_by_admin', read_only=True, default=False)

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'profile_picture', 'role', 'is_active',
                  'date_joined', 'created_by_admin', 'is_created_by_admin']

    def get_role(self, obj):
        return 'Admin' if obj.is_staff or obj.is_superuser else 'User'


class AdminProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminProfile
        fields = [
            'id', 'full_name', 'email', 'username', 'phone', 'role',
            'date_of_birth', 'gender', 'location', 'language', 'bio',
            'profile_image', 'profile_image_url'
        ]
        read_only_fields = ['id', 'role', 'email', 'username']

    def get_profile_image_url(self, obj):
        if obj.profile_image and hasattr(obj.profile_image, 'url') and obj.profile_image.name:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None

    def validate_gender(self, value):
        if value:
            clean_value = re.sub(r"['\"]+", "", str(value)).strip().title()
            if clean_value not in ['Male', 'Female']:
                raise serializers.ValidationError('Gender must be "Male" or "Female"')
            return clean_value
        return None
        
class AadhaarVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AadhaarVerification
        fields = ['id', 'aadhaar_number', 'aadhaar_image', 'status', 'verified_at', 
                  'rejection_reason', 'created_at', 'updated_at']
        read_only_fields = ['status', 'verified_at', 'rejection_reason', 'created_at', 'updated_at']

    def validate_aadhaar_number(self, value):
        if len(value) != 12 or not value.isdigit():
            raise serializers.ValidationError("Aadhaar number must be 12 digits")
        return value


class AdminProfileListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True) 
    profile_picture = serializers.SerializerMethodField()
    has_aadhaar = serializers.SerializerMethodField()
    aadhaar_status = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'user_id', 'email', 'username', 'phone', 
            'full_name', 'profile_picture', 'gender', 'height', 'date_of_birth', 
            'religion', 'district', 'city', 'state', 'country', 
            'occupation', 'verification_status', 'rejection_reason',
            'has_aadhaar', 'aadhaar_status', 'created_at'
        ]

    def get_profile_picture(self, obj):
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            request = self.context.get('request')
            return request.build_absolute_uri(obj.profile_picture.url) if request else obj.profile_picture.url
        return None

    def get_has_aadhaar(self, obj):
        return AadhaarVerification.objects.filter(user=obj.user).exists()

    def get_aadhaar_status(self, obj):
        try:
            verification = AadhaarVerification.objects.get(user=obj.user)
            return verification.status
        except AadhaarVerification.DoesNotExist:
            return None


class AdminProfileDetailSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = AdminProfile 
        fields = [
            'id', 'full_name', 'email', 'username', 'phone', 'role', 
            'date_of_birth', 'gender', 'location', 'language', 'bio',
            'profile_image', 'profile_image_url'
        ]
        read_only_fields = ['id', 'role', 'email', 'username']

    def get_profile_image_url(self, obj):
        request = self.context.get('request')
        if obj.profile_image:
            return request.build_absolute_uri(obj.profile_image.url) if request else obj.profile_image.url
        return None

    def validate_gender(self, value):
        if value:
            value = str(value).strip().lower()
            if value not in ['male', 'female']:
                raise serializers.ValidationError('Gender must be "male" or "female"')
        return value

    def update(self, instance, validated_data):
        if 'profile_image' in validated_data:
            new_image = validated_data.get('profile_image')
            if instance.profile_image and new_image:
                instance.profile_image.delete(save=False)
        return super().update(instance, validated_data)
    
class SuccessStorySerializer(serializers.ModelSerializer):
    image_one = serializers.ImageField(required=False, allow_null=True) 
    image_two = serializers.ImageField(required=False, allow_null=True) 

    class Meta:
        model = SuccessStory
        fields = ['id', 'partner_one_name', 'partner_two_name', 'marriage_date',
                  'location', 'story_text', 'image_one', 'image_two', 'created_at']

    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if instance.image_one:
            rep['image_one'] = request.build_absolute_uri(instance.image_one.url) if request else instance.image_one.url
        if instance.image_two:
            rep['image_two'] = request.build_absolute_uri(instance.image_two.url) if request else instance.image_two.url
        return rep

class SubscriptionPlanSerializer(serializers.ModelSerializer):
   
    price = serializers.CharField(required=True)
    duration_months = serializers.CharField(required=True)
    features = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False
    )

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'price', 'duration_months',
            'features', 'badge_color', 'is_free', 'is_active', 'created_at'
        ]

    def to_internal_value(self, data):
        # "₹299" → 299
        if 'price' in data and data['price'] is not None:
            price_str = str(data['price'])
            price_clean = re.sub(r'[^\d]', '', price_str)
            data['price'] = int(price_clean) if price_clean else 0

        # "6 Months" → 6
        if 'duration_months' in data and data['duration_months'] is not None:
            duration_str = str(data['duration_months'])
            duration_clean = re.sub(r'[^\d]', '', duration_str)
            data['duration_months'] = int(duration_clean) if duration_clean else 1

       
        if 'features' in data and isinstance(data['features'], str):
            data['features'] = [f.strip() for f in data['features'].split(',') if f.strip()]

        return super().to_internal_value(data)

class AdminPaymentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'user_name', 'user_email', 'plan_name', 'amount', 'transaction_id', 'status', 'created_at'] # ✅ created_at
        
class ProfileImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileImage
        fields = ['id', 'image']
            