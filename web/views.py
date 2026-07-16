from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from advisors.models import AdvisorDefinition, Conversation, Message, MessageRole
from advisors.services import AdvisorService
from core.models import Cohort, Run, UserRole
from engine.services import get_or_create_week_instance, submit_week, view_briefing
from scoring.models import Benchmark, ScoreRecord
from scoring.services import finalize_score, student_benchmark_payload
from weeks.registry import registry


def _run_for_user(user):
    return Run.objects.select_related('team__cohort').filter(team__members=user).first()


@login_required
def student_briefing(request):
    run = _run_for_user(request.user)
    if not run:
        return HttpResponseForbidden('No run is assigned to this user.')
    instance = view_briefing(run)
    module = registry.get(instance.week_number)
    tier = run.team.cohort.tier
    briefing = (
        module.briefing_for_run(tier, run)
        if hasattr(module, 'briefing_for_run') else
        module.briefing(tier)
    )
    return render(request, 'web/student_briefing.html', {
        'run': run,
        'week_instance': instance,
        'briefing': briefing,
        'artifacts': module.artifacts(tier),
        'decision_spec': module.decision_spec(tier),
        'advisors': AdvisorDefinition.objects.filter(active=True),
    })


@login_required
def advisor_consultation(request, advisor_id):
    run = _run_for_user(request.user)
    if not run:
        return HttpResponseForbidden('No run is assigned to this user.')
    advisor = get_object_or_404(AdvisorDefinition, id=advisor_id, active=True)
    instance = get_or_create_week_instance(run)
    conversation, _ = Conversation.objects.get_or_create(
        run=run,
        week_number=instance.week_number,
        advisor=advisor,
    )
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                conversation=conversation,
                role=MessageRole.STUDENT,
                content=content,
            )
            module = registry.get(instance.week_number)
            AdvisorService().respond(
                advisor=advisor,
                conversation=conversation,
                run_state=run.state,
                week_context=module.advisor_context(advisor.key, run.team.cohort.tier, run.state),
                tier=run.team.cohort.tier,
            )
    return render(request, 'web/advisor.html', {'conversation': conversation})


@login_required
def submit_decision(request):
    run = _run_for_user(request.user)
    if not run:
        return HttpResponseForbidden('No run is assigned to this user.')
    if request.method != 'POST':
        return redirect('web:student_briefing')
    instance = get_or_create_week_instance(run)
    module = registry.get(instance.week_number)
    payload = {}
    for field in module.decision_spec(run.team.cohort.tier).fields:
        if field.field_type == 'boolean':
            payload[field.key] = field.key in request.POST
        else:
            payload[field.key] = request.POST.get(field.key)
    submit_week(
        instance,
        structured_payload=payload,
        deliverable_text=request.POST.get('deliverable_text', ''),
        submitted_by=request.user,
    )
    return redirect('web:student_briefing')


@login_required
def instructor_score(request, score_id):
    if request.user.role != UserRole.INSTRUCTOR:
        return HttpResponseForbidden('Instructor access required.')
    score = get_object_or_404(ScoreRecord, id=score_id)
    if request.method == 'POST':
        instructor_scores = {
            'strategic_judgment': request.POST.get('strategic_judgment', 0),
            'execution_consequence': request.POST.get('execution_consequence', 0),
            'coherence': request.POST.get('coherence', 0),
            'deliverable_quality': request.POST.get('deliverable_quality', 0),
        }
        finalize_score(
            score,
            instructor_scores=instructor_scores,
            instructor_components={
                'rubric_notes': request.POST.get('rubric_notes', ''),
                'plan_sound': 'plan_sound' in request.POST,
            },
            graded_by=request.user,
        )
        return redirect('admin:scoring_scorerecord_change', score.id)
    return render(request, 'web/instructor_score.html', {'score': score})


@login_required
def benchmark_view(request, cohort_id, after_week):
    cohort = get_object_or_404(Cohort, id=cohort_id)
    benchmark = get_object_or_404(Benchmark, cohort=cohort, after_week=after_week)
    if not benchmark.is_revealed and request.user.role != UserRole.INSTRUCTOR:
        return HttpResponseForbidden('Benchmark has not been revealed.')
    return render(request, 'web/benchmark.html', {
        'benchmark': benchmark,
        'benchmark_payload': student_benchmark_payload(benchmark),
    })

# Create your views here.
