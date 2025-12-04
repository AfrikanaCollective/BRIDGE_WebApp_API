from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied

class ApprovedUserBackend(ModelBackend):
    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and user.is_approved