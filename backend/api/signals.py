from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.dispatch import receiver
from django.core.signing import TimestampSigner
from allauth.account.signals import user_signed_up

from .models import CustomUser

import logging, logging.config
logging.config.dictConfig(settings.LOGGING)

@receiver(post_save, sender=CustomUser)
def send_request_approval_app(sender, instance, created, **kwargs):

    frontend_url = getattr(settings, "FRONTEND_URL", "https://bridge.kemri-wellcome.org/dataclerk-ai")
    if frontend_url.endswith("/api"):
        frontend_url = frontend_url.rsplit("/api", 1)[0]

    #if created:
    if instance.profile_completed and not (instance.is_approved or created):
            signer = TimestampSigner()
            token = signer.sign(instance.id)  # e.g. "42:abc123sig"
            approval_url = f"{frontend_url}/approve-user/{instance.id}?token={token}"  
            # Or backend API URL if superuser approves via API call

            send_mail(
                subject="the data BRIDGE project: New user approval required",
                message=f"A new user has registered through web app: {instance.email}. Approve here: {approval_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.EMAIL_HOST_USER],
                fail_silently=False,
            )
            

@receiver(post_save, sender=CustomUser)
def send_approval_email(sender, instance, created, **kwargs):
    """
    Sends email when a user is approved.
    """
    # Only send email when the user is updated (not created)
    if not created and instance.is_approved and not instance.is_notified:
        subject = "the data BRIDGE project: Your account has been approved"
        message = (
            f"Hello {instance.get_full_name() or instance.email},\n\n"
            "Your account has been approved by the administrator.\n"
            "You can now log in to the system.\n\n"
            "Best regards,\nAI Clerk Team"
        )
        recipient_list = [instance.email]
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
        )


@receiver(user_signed_up)
def send_request_approval_google(request, user, **kwargs):

    frontend_url = getattr(settings, "FRONTEND_URL", "https://bridge.kemri-wellcome.org/dataclerk-ai")
    if frontend_url.endswith("/api"):
        frontend_url = frontend_url.rsplit("/api", 1)[0]

    signer = TimestampSigner()
    token = signer.sign(user.id)  # e.g. "42:abc123sig"
    
    approval_url = f"{frontend_url}/approve-user/{user.id}?token={token}"  
    # Or backend API URL if superuser approves via API call

    send_mail(
        subject="the data BRIDGE project: New user approval required",
        message=f"A new user has registered through Google: {user.email}. Approve here: {approval_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
