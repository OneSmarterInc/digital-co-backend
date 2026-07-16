from django.db import migrations


def seed_week3(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=3,
        defaults={
            'title': 'The Reckoning',
            'module_path': 'weeks.week3.Week3Module',
            'active': True,
        },
    )


def unseed_week3(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=3, module_path='weeks.week3.Week3Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0004_week2_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week3, unseed_week3),
    ]
