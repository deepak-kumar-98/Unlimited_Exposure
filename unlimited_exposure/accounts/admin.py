from django.contrib import admin
from .models import PlansAndFeature, Profile, Organization, OrganizationMember, Transaction, InvitationToken

admin.site.register(PlansAndFeature)
admin.site.register(Profile)
admin.site.register(Organization)
admin.site.register(OrganizationMember)
admin.site.register(Transaction)
admin.site.register(InvitationToken)
