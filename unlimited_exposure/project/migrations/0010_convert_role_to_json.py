# Generated manually to convert role strings to JSON arrays
import json
from django.db import migrations


def convert_role_to_json(apps, schema_editor):
    """Convert existing string role values to JSON arrays"""
    Agent = apps.get_model('project', 'Agent')
    
    for agent in Agent.objects.all():
        if agent.role and isinstance(agent.role, str):
            # Convert string to a single-item list
            agent.role = json.dumps([agent.role])
            agent.save(update_fields=['role'])


def reverse_conversion(apps, schema_editor):
    """Reverse: Convert JSON arrays back to strings"""
    Agent = apps.get_model('project', 'Agent')
    
    for agent in Agent.objects.all():
        if agent.role:
            try:
                role_list = json.loads(agent.role)
                if isinstance(role_list, list) and len(role_list) > 0:
                    agent.role = role_list[0]
                    agent.save(update_fields=['role'])
            except (json.JSONDecodeError, TypeError):
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0009_alter_systemsettings_organization'),
    ]

    operations = [
        migrations.RunPython(convert_role_to_json, reverse_conversion),
    ]
