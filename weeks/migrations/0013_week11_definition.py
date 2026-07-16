from django.db import migrations


def seed_week11(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=11,
        defaults={
            'title': 'The Reckoning of Trust',
            'module_path': 'weeks.week11.Week11Module',
            'active': True,
        },
    )


def unseed_week11(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=11, module_path='weeks.week11.Week11Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0012_week10_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week11, unseed_week11),
    ]
