from django.db import migrations


def seed_week13(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=13,
        defaults={
            'title': 'The Audit',
            'module_path': 'weeks.week13.Week13Module',
            'active': True,
        },
    )


def unseed_week13(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=13, module_path='weeks.week13.Week13Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0014_week12_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week13, unseed_week13),
    ]
