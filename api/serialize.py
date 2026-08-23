"""Serialization helpers for the JSON API.

The engine returns frozen dataclasses (Briefing, DecisionSpec, Artifact) and the
week decision forms are dynamic, so these helpers turn those into plain JSON the
Next.js frontend can render without knowing anything about the Python types.
"""
from advisor_agents.turn_cap import is_group_capped
from advisors.models import AdvisorDefinition
from weeks.models import WeekInstanceStatus


def week_status(instance):
    """The one payload that fixes the 'can't tell if it's submitted' gap."""
    return {
        'week_number': instance.week_number,
        'status': instance.status,
        'submitted': instance.status in (WeekInstanceStatus.SUBMITTED, WeekInstanceStatus.SCORED),
        'scored': instance.status == WeekInstanceStatus.SCORED,
    }


def briefing_json(briefing, preamble=''):
    """The standing briefing, plus this firm's own opening if one was written.

    The briefing itself is identical for every firm; the preamble is the only
    firm-specific text on the page, which is why it travels as its own field
    rather than being spliced into the body.
    """
    return {
        'title': briefing.title,
        'body': briefing.body,
        'exec_reads': list(briefing.exec_reads),
        'signals': list(briefing.signals),
        'preamble': preamble or '',
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


def group_session_json(session):
    """The war-room round: its advisor roster and the full shared transcript.

    Each turn carries the speaker's display name (and the advisor's json, so the
    client can show a portrait) and 'you' for the student. `capped` mirrors the
    backend group turn cap so the client can retire the compose box in step."""
    defs = {d.key: d for d in AdvisorDefinition.objects.filter(key__in=session.active_advisors)}
    active = [advisor_json(defs[k]) for k in session.active_advisors if k in defs]

    turns = []
    student_turns = 0
    for turn in session.turns.order_by('created_at', 'id'):
        if turn.speaker == 'student':
            student_turns += 1
            speaker_name, advisor = 'You', None
        else:
            advisor_def = defs.get(turn.speaker)
            speaker_name = advisor_def.name if advisor_def else turn.speaker
            advisor = advisor_json(advisor_def) if advisor_def else None
        turns.append({
            'id': turn.id,
            'speaker': turn.speaker,
            'speaker_name': speaker_name,
            'advisor': advisor,
            'content': turn.content,
            'created_at': turn.created_at.isoformat(),
        })

    # A room bills the cohort's hourly rate once per advisor seated in it, so the
    # client can state the price before the student opens their mouth.
    rate = session.run.team.cohort.advisor_hourly_rate or 0
    advisor_count = len(session.active_advisors or [])

    return {
        'session_id': session.id,
        'week_number': session.week_number,
        'active_advisors': active,
        'turns': turns,
        'student_turns': student_turns,
        'capped': is_group_capped(student_turns),
        'advisor_hourly_rate': rate,
        'advisor_count': advisor_count,
        'hourly_cost': rate * advisor_count,
    }


def score_record_json(score):
    instance = score.week_instance
    # WeekInstance.submission is the OneToOne set when the week is submitted
    # (None before then). It used to be read as `.submissions` (plural), which
    # doesn't exist and raised AttributeError — 500-ing the whole grading queue
    # the moment any week was submitted, so submissions never reached grading.
    submission = instance.submission
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
        # Grading context: what the firm actually sent, so the grader
        # never grades blind. Additive; nothing existing changes shape.
        'deliverable_text': submission.deliverable_text if submission else '',
        'decisions': submission.structured_payload if submission else {},
        # Graded weeks leave the queue, and the written answers were then
        # unreachable — but Week 13's board audit and the Week 14 debrief both
        # need them read back weeks later, as does any grade query. Carry the
        # grading record so a graded week can be reopened read-only.
        'graded_at': score.graded_at.isoformat() if score.graded_at else None,
        'graded_by': (
            (score.graded_by.get_full_name() or score.graded_by.username)
            if score.graded_by_id else None
        ),
        'anchor_strength': (
            instance.run.state.get('through_lines', {}).get('coherence', {}).get('anchor_strength')
        ),
        'coherence_anchor': instance.run.state.get('coherence_anchor', ''),
        'feedback': score.feedback,
        # What this firm was shown above the briefing that round, so the
        # instructor reads the same page the firm did.
        'preamble': instance.preamble,
        'preamble_problem': instance.preamble_problem,
        # The engine's read of the written deliverable, with its reasoning.
        # Surfaced so the proposal can be judged against the grader's own view
        # before it is trusted — and so a failed call reads as "not assessed"
        # rather than as a considered zero.
        'quality_proposal': score.auto_components.get('deliverable_quality_proposal') or {},
    }