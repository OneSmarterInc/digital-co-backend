from django.db import migrations


def seed_week6(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=6,
        defaults={
            'title': 'The Platform Question',
            'module_path': 'weeks.week6.Week6Module',
            'active': True,
        },
    )


def unseed_week6(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=6, module_path='weeks.week6.Week6Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0007_week5_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week6, unseed_week6),
    ]
