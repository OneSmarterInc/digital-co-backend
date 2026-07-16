from django.db import migrations


def seed_stub_week(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.update_or_create(
        week_number=1,
        defaults={
            'title': 'Foundation Stub Week',
            'module_path': 'weeks.stub.StubWeekModule',
            'active': True,
        },
    )


def unseed_stub_week(apps, schema_editor):
    WeekDefinition = apps.get_model('weeks', 'WeekDefinition')
    WeekDefinition.objects.filter(week_number=1, module_path='weeks.stub.StubWeekModule').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('weeks', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_stub_week, unseed_stub_week),
    ]
