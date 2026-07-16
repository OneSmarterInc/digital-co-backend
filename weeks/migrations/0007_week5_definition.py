from django.db import migrations


def seed_week5(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=5,
        defaults={
            'title': 'The Read',
            'module_path': 'weeks.week5.Week5Module',
            'active': True,
        },
    )


def unseed_week5(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=5, module_path='weeks.week5.Week5Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0006_week4_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week5, unseed_week5),
    ]
