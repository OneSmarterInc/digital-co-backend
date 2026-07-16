from django.db import migrations


def seed_week1(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=1,
        defaults={
            'title': 'The Inheritance',
            'module_path': 'weeks.week1.Week1Module',
            'active': True,
        },
    )


def unseed_week1(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=1,
        defaults={
            'title': 'Foundation Stub Week',
            'module_path': 'weeks.stub.StubWeekModule',
            'active': True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0002_seed_stub_week'),
    ]

    operations = [
        migrations.RunPython(seed_week1, unseed_week1),
    ]
