# accounts/backends.py
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # ഇവിടെ വരുന്നത് ഇമെയിൽ ആണോ യൂസർനെയിം ആണോ എന്ന് നോക്കാതെ ഇമെയിൽ വെച്ച് സെർച്ച് ചെയ്യും
        email = username or kwargs.get('email')
        if email:
            email = email.lower().strip()
        try:
            user = User.objects.get(email__iexact=email)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None