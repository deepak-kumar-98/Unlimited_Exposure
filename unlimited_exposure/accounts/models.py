import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User



class PlansAndFeature(models.Model):
    name = models.CharField(max_length=100, unique=False)
    allowed_no_of_projects = models.CharField(max_length=100)
    allowed_no_of_content = models.CharField(max_length=100)
    allowed_no_of_queries = models.CharField(max_length=100)
    plan_data_message = models.JSONField(default=list, null=True)
    sub_text = models.CharField(max_length=100, null=True)
    price = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name



# class Profile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     address = models.CharField(max_length=200, blank=True, null=True)
#     billing_address = models.TextField(blank=True, null=True)
#     profile_image_url = models.CharField(max_length=1000, blank=True, null=True)

#     subscription = models.ForeignKey(
#         PlansAndFeature, on_delete=models.DO_NOTHING, blank=True, null=True
#     )

#     created_organization = models.OneToOneField(
#         "Organization",
#         null=True,
#         blank=True,
#         on_delete=models.SET_NULL,
#         related_name="creator_profile"
#     )

#     no_of_queries = models.PositiveIntegerField(default=0)
#     no_of_content = models.PositiveIntegerField(default=0)
#     no_of_projects = models.PositiveIntegerField(default=0)

#     plan_expiry_at = models.DateTimeField(null=True, blank=True)
#     plan_created_at = models.DateTimeField(auto_now_add=True)
#     is_plan_expired = models.BooleanField(default=False)

#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return self.user.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    organization = models.ForeignKey(
        "Organization",
        on_delete=models.CASCADE,
        related_name="profiles"
    )

    address = models.CharField(max_length=200, blank=True, null=True)
    billing_address = models.TextField(blank=True, null=True)
    profile_image_url = models.CharField(max_length=1000, blank=True, null=True)

    subscription = models.ForeignKey(
        PlansAndFeature, on_delete=models.DO_NOTHING, blank=True, null=True
    )

    no_of_queries = models.PositiveIntegerField(default=0)
    no_of_content = models.PositiveIntegerField(default=0)
    no_of_projects = models.PositiveIntegerField(default=0)

    plan_expiry_at = models.DateTimeField(null=True, blank=True)
    plan_created_at = models.DateTimeField(auto_now_add=True)
    is_plan_expired = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email

    


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)

    owner = models.ForeignKey(
        "Profile",
        on_delete=models.CASCADE,
        related_name="owned_organizations",
        null=True,     # ✅ REQUIRED
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class OrganizationMember(models.Model):
    OWNER = 'owner'
    ADMIN = 'admin'
    USER = 'user'
    ROLES = [
        (OWNER, 'owner'),
        (ADMIN, 'admin'),
        (USER, 'user'),
    ]
    organization = models.ForeignKey(
        Organization, related_name='organizations_name', on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        Profile, related_name='organization_members', on_delete=models.CASCADE, null=True
    )
    email = models.EmailField(null=False)
    role = models.CharField(max_length=255, choices=ROLES)
    added_to_organization = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # is_deleted = models.BooleanField(default=False)
    invitation_accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('organization', 'email')

    def save(self, *args, **kwargs):
        if not self.email and self.user:
            self.email = self.user.user.email
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.id)