from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
import traceback

from accounts.const import (
    EMAIL_DESCRIPTION_FORGET_PASSWORD,
    EMAIL_DESCRIPTION_REGISTER_USER,
    EMAIL_DESCRIPTION_RESEND_VERIFICATION_MAIL,
)


def SendUserEmail(
    to_email,
    email_type,
    token=None,
    username=None,
    Invitation_token=None,
    Extra_info=None,
):
    """
    Unified email sender using SMTP.
    Compatible with RegisterUser & VerifyAccount views.
    """

    try:

        frontend_url = settings.FRONTEND_URL.rstrip("/")
        message = ""
        mail_subject = ""

        # =========================
        # AUTH EMAILS
        # =========================
        if email_type.startswith("auth:"):
            email_action = email_type.split(":")[1]

            if email_action == "account-activate":
                mail_subject = "Confirm Your Unlimited Exposure Account Registration"
                url_link = f"{frontend_url}/activate/{token}"
                description = EMAIL_DESCRIPTION_REGISTER_USER

            elif email_action == "Forgot":
                mail_subject = "Password Reset Request for Your Unlimited Exposure Account"
                url_link = f"{frontend_url}/reset-password/{token}"
                description = EMAIL_DESCRIPTION_FORGET_PASSWORD

            elif email_action == "Verify":
                mail_subject = "Verify Your Email Address for Your Unlimited Exposure Account"
                url_link = f"{frontend_url}/activate/{token}"
                description = EMAIL_DESCRIPTION_RESEND_VERIFICATION_MAIL

            else:
                raise ValueError("Invalid auth email type")

            message = render_to_string(
                "email_template.html",
                {
                    "url_link": url_link,
                    "description": description,
                    "email_type": email_action,
                    "username": username,
                },
            )

        # =========================
        # ORGANIZATION INVITATION
        # (kept for future use)
        # =========================
        elif email_type.startswith("organization_invitation:"):
            email_action = email_type.split(":")[1]
            Extra_info = Extra_info or {}

            organization_name = Extra_info.get("organization_name", "Organization")
            invited_by = Extra_info.get("invited_by", "Admin")
            organization_role = Extra_info.get("organization_role", "member")

            mail_subject = f"You're Invited to Join {organization_name}"
            url_link = f"{frontend_url}/activate/?invitation-token={Invitation_token}&email={to_email}"

            message = render_to_string(
                "organization_invitation.html",
                {
                    "url_link": url_link,
                    "username": username,
                    "organization_name": organization_name,
                    "organization_role": organization_role,
                    "invited_by": invited_by,
                },
            )

        else:
            raise ValueError("Email type not supported")

        # =========================
        # SEND EMAIL (SMTP)
        # =========================
        email_message = EmailMessage(
            subject=mail_subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        email_message.content_subtype = "html"
        email_message.send(fail_silently=False)

        return True

    except Exception as e:
        print("❌ Failed to send email")
        print(traceback.format_exc())
        raise e
