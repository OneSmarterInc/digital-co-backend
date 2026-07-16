from django.db import migrations


def seed_week4(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=4,
        defaults={
            'title': 'The Foundation',
            'module_path': 'weeks.week4.Week4Module',
            'active': True,
        },
    )


def unseed_week4(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=4, module_path='weeks.week4.Week4Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0005_week3_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week4, unseed_week4),
    ]
