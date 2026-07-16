from django.db import migrations


def seed_week10(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=10,
        defaults={
            'title': 'The Breach',
            'module_path': 'weeks.week10.Week10Module',
            'active': True,
        },
    )


def unseed_week10(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=10, module_path='weeks.week10.Week10Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0011_week9_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week10, unseed_week10),
    ]
