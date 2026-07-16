from django.db import migrations


def seed_week7(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=7,
        defaults={
            'title': 'The Squeeze',
            'module_path': 'weeks.week7.Week7Module',
            'active': True,
        },
    )


def unseed_week7(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=7, module_path='weeks.week7.Week7Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0008_week6_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week7, unseed_week7),
    ]
