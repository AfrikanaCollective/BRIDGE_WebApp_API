from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

class CustomGoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        sociallogin.state['next'] = '/api/token/'
        return user