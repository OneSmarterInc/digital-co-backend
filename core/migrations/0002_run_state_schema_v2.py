from copy import deepcopy

from django.db import migrations


def migrate_state_to_v2(apps, schema_editor):
    Run = apps.get_model('core', 'Run')
    for run in Run.objects.all():
        state = deepcopy(run.state or {})
        state['schema_version'] = 2
        gates = state.setdefault('gates', {})
        if 'ot_security' in gates and 'security_ot' not in gates:
            gates['security_ot'] = gates.pop('ot_security')
        gates.setdefault('security_ot', {'state': 'open', 'set_week': None, 'detonated': False})
        gates.setdefault('budget_credibility', {'state': 'open', 'set_week': None, 'detonated': False})
        gates.pop('ot_security', None)
        state.pop('board_confidence', None)
        Run.objects.filter(pk=run.pk).update(state=state)


def migrate_state_to_v1(apps, schema_editor):
    Run = apps.get_model('core', 'Run')
    for run in Run.objects.all():
        state = deepcopy(run.state or {})
        state['schema_version'] = 1
        gates = state.setdefault('gates', {})
        if 'security_ot' in gates and 'ot_security' not in gates:
            gates['ot_security'] = gates.pop('security_ot')
        Run.objects.filter(pk=run.pk).update(state=state)


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_state_to_v2, migrate_state_to_v1),
    ]
