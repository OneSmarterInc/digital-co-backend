from django.db import migrations


def seed_week14(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=14,
        defaults={
            'title': 'The Synthesis',
            'module_path': 'weeks.week14.Week14Module',
            'active': True,
        },
    )


def unseed_week14(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=14, module_path='weeks.week14.Week14Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0015_week13_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week14, unseed_week14),
    ]
