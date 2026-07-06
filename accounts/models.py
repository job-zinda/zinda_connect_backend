from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone

class User(AbstractUser):
    PROFILE_CHOICES = (
        ('self', 'Self'),
        ('parent', 'Parent'),
    )

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, blank=True, null=True) # ✅ unique=True remove cheythu
    profile_type = models.CharField(max_length=10, choices=PROFILE_CHOICES, null=True, blank=True)
    referral_id = models.CharField(max_length=50, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'name']

    class Meta:
        db_table = 'accounts_user'

    def __str__(self):
        return self.email

class Profile(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('Other', 'Other')]
    MARITAL_STATUS_CHOICES = [
        ('never_married', 'Never Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
        ('awaiting_divorce', 'Awaiting Divorce'),
    ]
    FAMILY_TYPE_CHOICES = [
        ('nuclear', 'Nuclear Family'),
        ('joint', 'Joint Family'),
        ('single_parent', 'Single Parent Family'),
        ('blended', 'Blended Family'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_type = models.CharField(max_length=10, choices=[('self', 'Self'), ('parent', 'Parent')])
   
    # STEP 1
    parent_name = models.CharField(max_length=100, null=True, blank=True) 
    relation_type = models.CharField(max_length=10, choices=[('father', 'Father'), ('mother', 'Mother')], null=True, blank=True)
    child_type = models.CharField(max_length=10, choices=[('son', 'Son'), ('daughter', 'Daughter')], null=True, blank=True)
    child_name = models.CharField(max_length=100, null=True, blank=True)
    
    # General Details
    full_name = models.CharField(max_length=100, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    height = models.CharField(max_length=10, null=True, blank=True)
    marital_status = models.CharField(max_length=100, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True) # ✅ Add cheythu

    # STEP 2: Religion & Community
    religion = models.CharField(max_length=50, null=True, blank=True)
    caste = models.CharField(max_length=50, null=True, blank=True)
    mother_tongue = models.CharField(max_length=50, null=True, blank=True)

    # STEP 3: Education & Career
    education = models.CharField(max_length=100, null=True, blank=True)
    occupation = models.CharField(max_length=100, null=True, blank=True)
    company = models.CharField(max_length=100, null=True, blank=True)
    annual_income = models.CharField(max_length=50, null=True, blank=True)

    # STEP 4: Location
    country = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    district = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)

    # STEP 5: Personal Details
    father_name = models.CharField(max_length=100, null=True, blank=True)
    mother_name = models.CharField(max_length=100, null=True, blank=True)
    family_type = models.CharField(max_length=50,choices=FAMILY_TYPE_CHOICES, null=True, blank=True )
    siblings = models.CharField(max_length=255, null=True, blank=True)
    about_me = models.TextField(null=True, blank=True)
    
    interests = models.JSONField(default=list, blank=True, null=True)
    
    language = models.CharField(max_length=50, default='English')
    # bio = models.TextField(blank=True)
    current_step = models.IntegerField(default=1)
    is_verified = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ✅ Admin Tracking Fields - Add cheyyuka
    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users'
    )
    is_created_by_admin = models.BooleanField(default=False)

    VERIFICATION_STATUS = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    verification_status = models.CharField(
        max_length=10,
        choices=VERIFICATION_STATUS,
        default='pending'
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_profiles'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'accounts_profile'

    def __str__(self):
        return f"{self.full_name or self.child_name} - {self.user.email}"

    def save(self, *args, **kwargs):
        if self.verification_status == 'verified':
            self.is_verified = True
        else:
            self.is_verified = False
        super().save(*args, **kwargs)

class Advertisement(models.Model):
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    title = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to='ads/')
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='image')
    link_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True) # ✅ default=True ensure cheyyuka
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title if self.title else f"Ad {self.id} ({self.file_type})"
    
class ProfileImage(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='profile_gallery/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Gallery Image for {self.profile.full_name or self.profile.user.email}"


# 🚫 1. Blocked Users Model
class BlockedUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocking_users')
    blocked_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocked_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'blocked_user')

    def __str__(self):
        return f"{self.user.username} blocked {self.blocked_user.username}"


# ⚙️ 2. Account Preferences & Privacy Model (OneToOne with User)


class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Privacy
    profile_visibility = models.CharField(max_length=20, default='Everyone')
    last_seen = models.BooleanField(default=False)
    online_status = models.BooleanField(default=True)
    photo_visibility = models.CharField(max_length=20, default='Everyone')
    contact_visibility = models.CharField(max_length=20, default='Matches Only')
    activity_status = models.CharField(max_length=20, default='Everyone')

    # ✅ Account Preferences - New Defaults
    language = models.CharField(max_length=20, default='English')
    distance = models.CharField(max_length=20, default='Anywhere') # 50 km → Anywhere
    age_preference = models.CharField(max_length=20, default='All Ages') # New default
    show_me = models.CharField(max_length=20, default='Everyone') # Women → Everyone

    def __str__(self):
        return f"{self.user.username}'s Preferences"


# 🛠️ 3. Support Message Model
class SupportMessage(models.Model):
    SUBJECT_CHOICES = [
        ('Account Issue', 'Account Issue'),
        ('Payment Issue', 'Payment Issue'),
        ('Profile Issue', 'Profile Issue'),
        ('Technical Issue', 'Technical Issue'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_messages')
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    message = models.TextField(max_length=1000)
    attachment = models.FileField(upload_to='support_attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} by {self.user.username}"
# 🔔 1. Notification Settings Model
class NotificationSetting(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_setting')
    messages = models.BooleanField(default=True)
    matches = models.BooleanField(default=True)
    profile_views = models.BooleanField(default=True)
    likes = models.BooleanField(default=True)
    updates = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)

    def __str__(self):
        return f"Notification settings for {self.user.username}"
    
class NotificationSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_settings')
    messages = models.BooleanField(default=True)
    favourites = models.BooleanField(default=True)
    profile_views = models.BooleanField(default=True)
    likes = models.BooleanField(default=True)
    updates_news = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Notification Settings"
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.IntegerField(default=0)
    duration_months = models.IntegerField(default=1)
    features = models.JSONField(default=list, blank=True)
    badge_color = models.CharField(max_length=20, default="#6c757d")
    is_free = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True) # ✅ Add ചെയ്തു - public API filter ചെയ്യാൻ
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['price']

class UserSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    plan_name = models.CharField(max_length=50, default="Free Plan")
    price = models.IntegerField(default=0)
    next_billing_date = models.DateField(null=True, blank=True)
    card_digits = models.CharField(max_length=4, default="0000", blank=True)
    is_active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.plan_name}"

    @property
    def display_name(self):
        return self.plan.name if self.plan else self.plan_name

    @property
    def display_price(self):
        return self.plan.price if self.plan else self.price

    def activate(self, plan):
        """Plan activate ചെയ്യാൻ helper method"""
        self.plan = plan
        self.plan_name = plan.name
        self.price = plan.price
        self.is_active = True
        self.activated_at = timezone.now()
        self.expires_at = timezone.now() + timezone.timedelta(days=plan.duration_months * 30)
        self.next_billing_date = self.expires_at.date()
        self.cancelled_at = None 
        self.save()

    def deactivate(self):
        
        self.is_active = False
        self.cancelled_at = timezone.now()
        self.save()
        
# ⚠️ 3. Report Problem Model
class ReportedProblem(models.Model):
    ISSUE_CHOICES = [
        ('Bug', 'Bug'),
        ('Payment Problem', 'Payment Problem'),
        ('Login Issue', 'Login Issue'),
        ('Profile Issue', 'Profile Issue'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reported_problems')
    issue_type = models.CharField(max_length=30, choices=ISSUE_CHOICES)
    description = models.TextField(max_length=1000)
    attachment = models.FileField(upload_to='problem_attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.issue_type} reported by {self.user.username}"
    
class ProfileLike(models.Model):
    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_likes'
    )

    to_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
class FavouriteProfile(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('message', 'Message'),
        ('favourite', 'Favourite'),
        ('profile_view', 'Profile View'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    profile_id = models.IntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']



class Comment(models.Model):
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class ChatRoom(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('ignored', 'Ignored'),  # ✅ Add ചെയ്തു
    ]
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_rooms_1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_rooms_2')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # ✅ Add ചെയ്തു - Last message time track ചെയ്യാൻ

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user1', 'user2'], name='unique_chat_room'),
            models.UniqueConstraint(fields=['user2', 'user1'], name='unique_chat_room_reverse')
        ]
        ordering = ['-updated_at']  # ✅ Add ചെയ്തു - Latest chat മുകളിൽ വരാൻ


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    message_type = models.CharField(max_length=20, default='text')  # text, voice, image, system
    voice_file = models.FileField(upload_to='voice/', blank=True, null=True)
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    
    #  Delete functionality
    is_deleted_for_everyone = models.BooleanField(default=False)
    deleted_by = models.ManyToManyField(User, related_name='deleted_messages', blank=True)
    
    class Meta:
        ordering = ['created_at']
        

# 1. Admin Settings Model
class AdminSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_settings')
    profile_image = models.ImageField(upload_to='admin_profiles/', null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female')], null=True, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    language = models.CharField(max_length=20, default='english', choices=[
        ('english', 'English'),
        ('malayalam', 'Malayalam'),
        ('hindi', 'Hindi')
    ])
    bio = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=50, default='Admin') # ✅ Ithu add cheyyu
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} - Admin"

class AadhaarVerification(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='aadhaar_verification')
    aadhaar_number = models.CharField(max_length=12)
    aadhaar_image = models.ImageField(upload_to='aadhaar/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_aadhaars')

    def __str__(self):
        return f"{self.user.email} - {self.status}"
    
# accounts/models.py
class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    full_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=50, default='Admin')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female')], blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    language = models.CharField(max_length=50, default='English')
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='admin_profiles/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Admin Profile"


class SuccessStory(models.Model):
    image_one = models.ImageField(upload_to='success_stories/', blank=True, null=True)
    image_two = models.ImageField(upload_to='success_stories/', blank=True, null=True)
    partner_one_name = models.CharField(max_length=100)
    partner_two_name = models.CharField(max_length=100)
    marriage_date = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    story_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.partner_one_name} & {self.partner_two_name}"




class Payment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        null=True,  
        blank=True  
    )
    user_name = models.CharField(max_length=150)
    plan_name = models.CharField(max_length=100)
    amount = models.IntegerField()
    transaction_id = models.CharField(max_length=100)
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default="completed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class AdminPaymentMethod(models.Model):
    bank_name = models.CharField(max_length=100, default="UCO Bank")
    account_number = models.CharField(max_length=50, default="29720110039977")
    ifsc_code = models.CharField(max_length=20, default="UCBA0002972")
    account_holder = models.CharField(max_length=100, default="Muhammed Rafi.T")
    upi_id = models.CharField(max_length=100, default="mrafiajk-1@oksbi")
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    
    def __str__(self):
        return f"Admin Payment Details"
    
    class Meta:
        verbose_name = "Admin Payment Method"
        verbose_name_plural = "Admin Payment Methods"

