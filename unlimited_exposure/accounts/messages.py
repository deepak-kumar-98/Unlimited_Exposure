MESSAGES = {
    "success.account-created": "Account created successfully. Please verify your email",
    "success.email-verified": "Your account has been successfully verified",
    "error.email-verified": "The entered email is already registered and verified",
    "sign-up.user-exist": "Account already exists. Please log in or reset your password",
    "require.email": "Email is required",
    "require.password": "Password is required",
    "verify-email.link-expired": "Your verification link has expired. Please request a new link to complete the verification process",
    "verify-email.verification-link-expired": "The verification link has expired",
    "verify-email.send-email-msg": "If the email is registered, a verification link has been sent. Please check your inbox",
    "verify-email.check-email-msg": "The verification email has been resent. Please check your inbox",
    "forgot-password.password-reset-email": "If the email exists, a password reset email has been sent. Please check your inbox.",
    "sign-in.user-not-found": "User not found.",
    "sign-in.email-verify-error": "Email is not verified. Please check your inbox or click \"Verify Email\" to resend",
    "sign-in.invalid-credentials": "Invalid credentials. Please try again.",
}



def get_response_messages():
    return MESSAGES
