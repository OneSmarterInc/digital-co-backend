from django.db import migrations


def seed_week2(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=2,
        defaults={
            'title': 'The Alignment Confrontation',
            'module_path': 'weeks.week2.Week2Module',
            'active': True,
        },
    )


def unseed_week2(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=2, module_path='weeks.week2.Week2Module').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0003_week1_definition'),
    ]

    operations = [
        migrations.RunPython(seed_week2, unseed_week2),
    ]
