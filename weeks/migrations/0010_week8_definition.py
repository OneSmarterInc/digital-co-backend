from django.db import migrations


def seed_week8(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=8,
        defaults={
            'title': 'The Keystone',
            'module_path': 'weeks.week8.Week8Module',
            'active': True,
        },
    )


def unseed_week8(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=8, module_path='weeks.week8.Week8Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0009_week7_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week8, unseed_week8),
    ]
