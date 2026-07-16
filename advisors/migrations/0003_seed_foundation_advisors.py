from django.db import migrations


ADVISORS = [
    {
        'key': 'calloway',
        'name': 'Calloway',
        'title': 'Commercial Sponsor',
        'persona': 'Ambitious, market-facing, and impatient with internal drag.',
        'lane': 'Revenue, customer commitments, and commercial timing.',
        'bias': 'Overweights momentum and executive sponsorship.',
        'notices': 'Customer and market signals others may dismiss.',
        'capture_trap': 'Commercial urgency outruns operating capacity.',
    },
    {
        'key': 'reinhardt',
        'name': 'Reinhardt',
        'title': 'Board Operator',
        'persona': 'Measured, governance-minded, and allergic to vague claims.',
        'lane': 'Board confidence, governance, and enterprise risk.',
        'bias': 'Overweights defensibility and board optics.',
        'notices': 'Weak causal links in the team narrative.',
        'capture_trap': 'The team optimizes for presentation polish over action.',
    },
    {
        'key': 'petrillo',
        'name': 'Petrillo',
        'title': 'Operations Executive',
        'persona': 'Pragmatic, plant-aware, and direct.',
        'lane': 'Operations, OT constraints, and execution load.',
        'bias': 'Overweights operational continuity.',
        'notices': 'Hidden dependencies in field execution.',
        'capture_trap': 'The team preserves the current operating model too long.',
    },
    {
        'key': 'ferraro',
        'name': 'Ferraro',
        'title': 'Finance Executive',
        'persona': 'Numerate, skeptical, and focused on credibility.',
        'lane': 'Budget, sequencing, and financial commitments.',
        'bias': 'Overweights near-term financial certainty.',
        'notices': 'Unfunded assumptions and soft benefit claims.',
        'capture_trap': 'The team starves necessary capabilities to protect the plan.',
    },
    {
        'key': 'fischer',
        'name': 'Fischer',
        'title': 'Technology Executive',
        'persona': 'Architecture-minded, precise, and systems-oriented.',
        'lane': 'Platforms, integration, data, and technical sequencing.',
        'bias': 'Overweights architectural purity.',
        'notices': 'Technical debt and lock-in patterns.',
        'capture_trap': 'The team lets platform elegance displace business urgency.',
    },
    {
        'key': 'tran',
        'name': 'Tran',
        'title': 'Security Advisor',
        'persona': 'Calm, skeptical, and concrete about risk.',
        'lane': 'Security, controls, OT exposure, and resilience.',
        'bias': 'Overweights downside containment.',
        'notices': 'Security consequences buried inside operational decisions.',
        'capture_trap': 'The team freezes decisions to avoid risk.',
    },
]


def seed_advisors(apps, schema_editor):
    AdvisorDefinition = apps.get_model('advisors', 'AdvisorDefinition')
    for advisor in ADVISORS:
        AdvisorDefinition.objects.update_or_create(
            key=advisor['key'],
            defaults={**advisor, 'active': True},
        )


def unseed_advisors(apps, schema_editor):
    AdvisorDefinition = apps.get_model('advisors', 'AdvisorDefinition')
    AdvisorDefinition.objects.filter(key__in=[advisor['key'] for advisor in ADVISORS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('advisors', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(seed_advisors, unseed_advisors),
    ]
