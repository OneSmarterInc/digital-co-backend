"""Serialization helpers for the JSON API.

The engine returns frozen dataclasses (Briefing, DecisionSpec, Artifact) and the
week decision forms are dynamic, so these helpers turn those into plain JSON the
Next.js frontend can render without knowing anything about the Python types.
"""
from weeks.models import WeekInstanceStatus


def week_status(instance):
    """The one payload that fixes the 'can't tell if it's submitted' gap."""
    return {
        'week_number': instance.week_number,
        'status': instance.status,
        'submitted': instance.status in (WeekInstanceStatus.SUBMITTED, WeekInstanceStatus.SCORED),
        'scored': instance.status == WeekInstanceStatus.SCORED,
    }


def briefing_json(briefing):
    return {
        'title': briefing.title,
        'body': briefing.body,
        'exec_reads': list(briefing.exec_reads),
        'signals': list(briefing.signals),
    }


def artifacts_json(artifacts):
    return [{'title': a.title, 'body': a.body, 'kind': a.kind} for a in artifacts]


def decision_spec_json(spec):
    """Declarative form definition: the frontend renders each week from this."""
    return {
        'deliverable_prompt': spec.deliverable_prompt,
        'rubric_variant': spec.rubric_variant,
        'fields': [
            {
                'key': f.key,
                'label': f.label,
                'field_type': f.field_type,
                'required': f.required,
                'choices': list(f.choices),
            }
            for f in spec.fields
        ],
    }


def advisor_json(advisor):
    return {
        'id': advisor.id,
        'key': advisor.key,
        'name': advisor.name,
        'title': advisor.title,
        # Relative to the API root; clients prefix their API base URL.
        'image_url': f'/advisors/{advisor.id}/image/',
    }


def conversation_json(conversation):
    return {
        'advisor': advisor_json(conversation.advisor),
        'week_number': conversation.week_number,
        'messages': [
            {
                'id': message.id,
                'role': message.role,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
            }
            for message in conversation.messages.order_by('created_at', 'id')
        ],
    }


def score_record_json(score):
    instance = score.week_instance
    return {
        'id': score.id,
        'week_number': instance.week_number,
        'team_name': instance.run.team.name,
        'cohort': instance.run.team.cohort.name,
        'status': instance.status,
        'auto_scores': score.auto_components.get('scores', {}),
        'trap_flags': score.auto_components.get('trap_flags', []),
        'dimension_scores': score.dimension_scores(),
        'graded': score.graded_at is not None,
    }