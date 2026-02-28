from django.db import migrations

def create_default_basic_plan(apps, schema_editor):
    PlansAndFeature = apps.get_model('accounts', 'PlansAndFeature')
    Profile = apps.get_model('accounts', 'Profile')

    # 1. Ensure "Basic" plan exists
    basic_plan, created = PlansAndFeature.objects.get_or_create(
        name="Basic",
        defaults={
            "allowed_no_of_projects": "1",
            "allowed_no_of_content": "5",
            "allowed_no_of_queries": "10",
            "price": "0",
            "sub_text": "Basic Plan"
        }
    )

    # 2. Update all profiles that don't have a subscription
    from django.utils import timezone
    profiles_to_update = Profile.objects.filter(subscription__isnull=True)
    for profile in profiles_to_update:
        profile.subscription = basic_plan
        profile.plan_expiry_at = timezone.now() + timezone.timedelta(days=30)
        profile.plan_created_at = timezone.now()
        profile.is_plan_expired = False
        try:
            profile.no_of_projects = int(basic_plan.allowed_no_of_projects)
            profile.no_of_content = int(basic_plan.allowed_no_of_content)
            profile.no_of_queries = int(basic_plan.allowed_no_of_queries)
        except (ValueError, TypeError):
            pass
        profile.save()

def remove_default_basic_plan(apps, schema_editor):
    # Optional: logic to reverse the migration if needed
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_transaction'),
    ]

    operations = [
        migrations.RunPython(create_default_basic_plan, remove_default_basic_plan),
    ]
