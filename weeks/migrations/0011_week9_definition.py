from django.db import migrations


def seed_week9(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=9,
        defaults={
            'title': 'The Bet',
            'module_path': 'weeks.week9.Week9Module',
            'active': True,
        },
    )


def unseed_week9(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=9, module_path='weeks.week9.Week9Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0010_week8_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week9, unseed_week9),
    ]
