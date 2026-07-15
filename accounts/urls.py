# accounts/urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

# views.py-ൽ നിന്ന് ഇല്ലാത്ത get_admin_profile, update_admin_profile എന്നിവ ഒഴിവാക്കിയുള്ള ഇമ്പോർട്ട് ലിസ്റ്റ്
from .views import (
    AdminPaymentListView, AdminProfileListView, AdminSubscriptionPlanDetailView,
    AdminSubscriptionPlanListCreateView, AdminSubscriptionPlanView,
    AdminSuccessStoryDetailView, AdminSuccessStoryListCreateView, AdvertisementView, CreateRazorpayOrderView,
    FavouriteProfileView, MyFavouriteView, MyLikesView, MyMatchesView,
    RegisterView, LoginView, GetUserView, RemoveFavouriteView, UnlikeProfileView,
    UpdateProfileTypeView, SendOTPView, VerifyOTPView,
    ResetPasswordView, UpdateBasicDetailsView,
    UpdateReligionView, UpdateEducationView, AdminDashboardStatsView,
    AdminRecentRegistrationsView, AdminProfileView,
    UpdateLocationView, UpdatePersonalDetailsView, ProfileDetailsView, LikeProfileView,
    AllProfilesListView, UpdateProfileView, BlockUserView, UserPreferencesView, NotificationSettingView, UserSubscriptionView,
    AdminUsersView, AdminUserDetailView, AdminProfilesView, AdminVerifyProfileView,
    AadhaarVerificationView, AdminPaymentDetailsView, ProcessPlanPurchaseView, VerifyPaymentView,
    add_comment, chat_request_action, delete_messages_view, get_notifications,
    get_public_plans, get_success_stories_public, mark_notification_read, get_admin_user, 
    report_problem_api, send_image_message, send_support_message_api, 
    get_chat_rooms, create_or_get_chat, get_messages, send_message, send_voice_message,
    change_password
)

urlpatterns = [
    # ==================== USER AUTHENTICATION ====================
    path('login/', LoginView.as_view()),
    path('register/', RegisterView.as_view()),
    path('user/', GetUserView.as_view()),
    path('token/refresh/', TokenRefreshView.as_view()),
    path('change-password/', change_password, name='change_password'),
    path('forgot-password/send-otp/', SendOTPView.as_view()),
    path('forgot-password/verify-otp/', VerifyOTPView.as_view()),
    path('forgot-password/reset/', ResetPasswordView.as_view()),

    # ==================== USER PROFILE MANAGEMENT ====================
    path('profile/', UpdateProfileView.as_view(), name='profile'),
    path('profile/update-type/', UpdateProfileTypeView.as_view(), name='update_profile_type'),
    path('profile/basic-details/', UpdateBasicDetailsView.as_view()),
    path('profile/religion/', UpdateReligionView.as_view()),
    path('profile/education/', UpdateEducationView.as_view()),
    path('profile/location/', UpdateLocationView.as_view()),
    path('profile/personal-details/', UpdatePersonalDetailsView.as_view()),
    path("profile/<int:id>/", ProfileDetailsView.as_view(), name="profile_details"),
    path('profiles/', AllProfilesListView.as_view()),

    # ==================== LIKES & FAVOURITES ====================
    path("like-profile/", LikeProfileView.as_view(), name="like_profile"),
    path("unlike-profile/<int:profile_id>/", UnlikeProfileView.as_view()),
    path("favourite-profile/", FavouriteProfileView.as_view()),
    path("remove-favourite/<int:profile_id>/", RemoveFavouriteView.as_view()),
    path("my-likes/", MyLikesView.as_view()),
    path("my-favourites/", MyFavouriteView.as_view()),
    path("my-matches/", MyMatchesView.as_view(), name="my_matches"),
    path('block-user/', BlockUserView.as_view(), name='block_user'),

    # ==================== CHAT SYSTEM ====================
    path('chat-rooms/', get_chat_rooms, name='get_chat_rooms'),
    path('chat/create/', create_or_get_chat, name='create_chat'),
    path('chat/<int:room_id>/messages/', get_messages, name='get_messages'),
    path('chat/send-message/', send_message, name='send_message'),
    path('chat/send-voice/', send_voice_message, name='send-voice'),
    path('chat/send-image/', send_image_message, name='send_image_message'),
    path('chat/request-action/<int:room_id>/', chat_request_action, name='chat_request_action'),
    path('chat/delete-message/', delete_messages_view, name='delete_messages_view'),

    # ==================== NOTIFICATIONS & FEEDBACK ====================
    path('user-notifications/', get_notifications, name='get_notifications'),
    path('notifications/', NotificationSettingView.as_view(), name='notification_settings'),
    path('notifications/<int:notification_id>/read/', mark_notification_read, name='mark_notification_read'),
    path('add-comment/', add_comment, name='add_comment'),
    path('support/', send_support_message_api, name='support_message'),
    path('report-problem/', report_problem_api, name='report_problem'),
    path('preferences/', UserPreferencesView.as_view(), name='user_preferences'),
    path('ads/', AdvertisementView.as_view()),
    path('aadhaar-verification/', AadhaarVerificationView.as_view(), name='aadhaar-verification'),

    # ==================== SUBSCRIPTIONS & PAYMENTS ====================
    path('subscription/', UserSubscriptionView.as_view(), name='user_subscription'),
    path('payment/create-order/', CreateRazorpayOrderView.as_view(), name='create-order'),
    path('payment/process-purchase/', ProcessPlanPurchaseView.as_view(), name='process-purchase'),
    path('payment/verify/', VerifyPaymentView.as_view(), name='verify-payment'),

    # ==================== ADMIN OPERATIONS ====================
    path('admin/stats/', AdminDashboardStatsView.as_view(), name='admin-stats'),
    path('admin/recent-registrations/', AdminRecentRegistrationsView.as_view(), name='admin-recent-registrations'),
    path('admin/users/', AdminUsersView.as_view(), name='admin-users'),
    path('admin/users/<int:user_id>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    
    # 🛠️ വിട്ടുപോയ പ്രൊഫൈൽ ലിസ്റ്റ് യുആർഎൽ ഇവിടെ കൃത്യമായി ചേർത്തു:
    path('admin/profiles/', AdminProfilesView.as_view(), name='admin-profiles-list'),
    path('admin/profiles/<int:profile_id>/verify/', AdminVerifyProfileView.as_view(), name='admin-verify-profile'),
    path("admin-user/", get_admin_user, name="admin-user"),
    
    # സിംഗിൾ ക്ലാസ്സ് വ്യൂ റൂട്ട്
    path('admin/profile/', AdminProfileView.as_view(), name='admin-profile'),

    # Admin Management Features (Ads, Stories, Plans, Payments)
    path('admin/ads/', AdvertisementView.as_view(), name='admin-ads'),
    path('admin/ads/<int:pk>/', AdvertisementView.as_view(), name='admin-ad-detail'),
    path('admin/stories/', AdminSuccessStoryListCreateView.as_view(), name='admin-stories-list'),
    path('admin/stories/<int:pk>/', AdminSuccessStoryDetailView.as_view(), name='admin-story-detail'),
    path('admin/plans/', AdminSubscriptionPlanView.as_view(), name='admin-subscription-plans'),
    path('admin/plans/<int:pk>/', AdminSubscriptionPlanDetailView.as_view(), name='admin-plan-detail'),
    path('admin/payments/', AdminPaymentListView.as_view(), name='admin-payments-list'),
    path('payment/admin-details/', AdminPaymentDetailsView.as_view(), name='admin-payment-details'),
]