from django.db import migrations


def seed_week12(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=12,
        defaults={
            'title': 'The Reckoning of Cost',
            'module_path': 'weeks.week12.Week12Module',
            'active': True,
        },
    )


def unseed_week12(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=12, module_path='weeks.week12.Week12Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0013_week11_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week12, unseed_week12),
    ]
