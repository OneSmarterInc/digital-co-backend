"""Seed and play the four DigitalCo verification runs from the answer key.

For each run this enters the documented decision for every week, grades every
week, sets the Week 1 anchor strength, and lets the engine apply consequences,
then prints the live results (trap flags, gate timeline, through-line
endpoints, end-state flags, tier, accumulated totals) so they can be checked
against the answer key. Runs A, B, C play weeks 1-14; run D is two teams in one
cohort played through week 11 for the benchmark check.

Idempotent: it deletes anything it previously seeded (cohorts prefixed
"Verification " and users prefixed "seed_") before recreating.

Usage:
    python manage.py seed_verification_runs
"""
from copy import deepcopy

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Cohort, Run, RunStatus, Team, Tier, User, UserRole
from core.state import SCORE_DIMENSIONS
from engine.services import submit_week, view_briefing
from scoring.models import Benchmark
from scoring.services import finalize_score, reveal_benchmark
from weeks.tests import (
    week1_payload, week2_payload, week3_payload, week4_payload, week5_payload,
    week6_payload, week7_payload, week8_payload, week9_payload, week10_payload,
    week11_payload, week12_payload, week13_payload, week14_payload,
)

BUILDERS = {
    1: week1_payload, 2: week2_payload, 3: week3_payload, 4: week4_payload,
    5: week5_payload, 6: week6_payload, 7: week7_payload, 8: week8_payload,
    9: week9_payload, 10: week10_payload, 11: week11_payload, 12: week12_payload,
    13: week13_payload, 14: week14_payload,
}

# --- Run A: the sound path (every decision is the sound one) ---
RUN_A = {
    1: {'connected_products_disposition': 'continue', 's4_disposition': 'stabilize_map',
        'data_strategy_posture': 'pursue', 'early_action': 'ot_visibility_assessment',
        'ot_black_box_engaged': True, 'primary_stakeholder_anchor': 'calloway'},
    2: {'alignment_choice': 'transform_data_services', 'governance_included': True,
        'governance_has_stage_gates': True, 'governance_gives_business_voice': True,
        'calloway_positioning': 'team_recommendation_with_cover'},
    3: {'migration_fate': 'restructure', 'integrator_decision': 'renegotiate',
        'has_execution_plan': True, 'communication_posture': 'transparent_ownership'},
    4: {'sourcing_approach': 'core_context_split', 'differentiator_layer': 'own',
        'cloud_commitment': 'portability_protected'},
    5: {'portfolio.autonomy': 'watch', 'portfolio.digital_twins': 'pilot',
        'portfolio.additive_manufacturing': 'watch', 'portfolio.edge_ai_low_end': 'bet',
        'innovation_capability': 'embedded', 'meridian_response': 'strategic_conviction'},
    6: {'platform_decision': 'connected_services', 'investment_level': 'right_sized',
        'openness': 'scoped_with_data_rights'},
    7: {'vendor_response': 'renegotiate', 'communication_posture': 'transparent_ownership',
        'hedge_plan': True, 'ot_signal_addressed': True},
    8: {'rights_posture': 'shared_value', 'governance_built': True,
        'analytics_architecture': 'predictive'},
    9: {'deployment': 'predictive_maintenance_core', 'ai_sourcing': 'build_differentiating_rent_commodity',
        'vendor_concentration': 'hedged', 'shadow_ai_response': 'governed_with_plan'},
    10: {'containment': 'contained', 'disclosure': 'transparent',
         'ransom_decision': 'refuse', 'triage_approach': 'parallel'},
    11: {'rights_resolution': 'shared_value', 'public_response': 'reframe_and_offer',
         'legal_posture': 'settle_where_serves', 'trust_repair_plan': True},
    12: {'architecture': 'edge_and_repatriate', 'hyperscaler_decision': 'renegotiate',
         'finops_discipline': True},
    13: {'narrative_coherence': 'coherent', 'business_case': 'board_language',
         'ask_sizing': 'well_sized', 'hostile_question_handled': 'defended'},
    14: {'integration': 'genuine', 'consequence_reckoning': 'honest',
         'forward_strategy': 'grounded_in_real_position'},
}

# --- Run B: the all-traps path (every decision is a trap) ---
RUN_B = {
    1: {'connected_products_disposition': 'kill', 's4_disposition': 'commit_finish',
        'data_strategy_posture': 'slow_walk', 'early_action': 'premature_bold_move',
        'ot_black_box_engaged': False, 'primary_stakeholder_anchor': 'ferraro'},
    2: {'alignment_choice': 'balanced_split', 'governance_included': False,
        'governance_has_stage_gates': False, 'governance_gives_business_voice': False,
        'calloway_positioning': 'propose_safe_stabilization'},
    3: {'migration_fate': 'rescue', 'integrator_decision': 'take_accelerator',
        'has_execution_plan': False, 'communication_posture': 'blame_shift'},
    4: {'sourcing_approach': 'build_everything', 'differentiator_layer': 'rent',
        'cloud_commitment': 'sweet_deal_as_written'},
    5: {'portfolio.autonomy': 'bet', 'portfolio.digital_twins': 'bet',
        'portfolio.additive_manufacturing': 'bet', 'portfolio.edge_ai_low_end': 'ignore',
        'innovation_capability': 'separate_group', 'meridian_response': 'chase'},
    6: {'platform_decision': 'grand_platform', 'investment_level': 'grand_spend',
        'openness': 'open_unguarded'},
    7: {'vendor_response': 'switch', 'communication_posture': 'spin',
        'hedge_plan': False, 'ot_signal_addressed': False},
    8: {'rights_posture': 'land_grab', 'governance_built': False,
        'analytics_architecture': 'descriptive_only'},
    9: {'deployment': 'theater_scatter', 'ai_sourcing': 'build_everything',
        'vendor_concentration': 'single_hyperscaler', 'shadow_ai_response': 'ungoverned'},
    10: {'containment': 'overwhelmed', 'disclosure': 'spin_or_hide',
         'ransom_decision': 'pay', 'triage_approach': 'linear'},
    11: {'rights_resolution': 'hold_firm', 'public_response': 'fight',
         'legal_posture': 'defend', 'trust_repair_plan': False},
    12: {'architecture': 'centralize', 'hyperscaler_decision': 'committed_spend_discount',
         'finops_discipline': False},
    13: {'narrative_coherence': 'contradictory', 'business_case': 'technical_jargon',
         'ask_sizing': 'too_big', 'hostile_question_handled': 'folded'},
    14: {'integration': 'papered_over', 'consequence_reckoning': 'victory_narrative',
         'forward_strategy': 'describes_unbuilt_company'},
}


def _with_overrides(base, changes):
    out = deepcopy(base)
    for wk, fields in changes.items():
        out[wk] = {**out[wk], **fields}
    return out


# Run C: Run A but neglect the OT thread (W1 and W7 changes only).
RUN_C = _with_overrides(RUN_A, {
    1: {'early_action': 'other_credibility_move', 'ot_black_box_engaged': False},
    7: {'ot_signal_addressed': False},
})

# Run D team B: Run A but with the land-grab / hold-firm data-rights path.
RUN_D_B = _with_overrides(RUN_A, {
    6: {'openness': 'open_unguarded'},
    8: {'rights_posture': 'land_grab'},
    11: {'rights_resolution': 'hold_firm', 'public_response': 'fight', 'trust_repair_plan': False},
})


class Command(BaseCommand):
    help = "Seed and play the four verification runs from the answer key."

    def handle(self, *args, **opts):
        with transaction.atomic():
            Cohort.objects.filter(name__startswith='Verification ').delete()
            User.objects.filter(username__startswith='seed_').delete()

            grader = User.objects.create_user(
                username='seed_grader', password='seed-grader-pass',
                role=UserRole.INSTRUCTOR, is_staff=True, is_superuser=True,
            )

            self._run('Verification A', 'A', RUN_A, 'strong', 7, range(1, 15), grader)
            self._run('Verification B', 'B', RUN_B, 'weak', 1, range(1, 15), grader)
            self._run('Verification C', 'C', RUN_C, 'strong', 7, range(1, 15), grader)
            self._run_d(grader)

        self.stdout.write(self.style.SUCCESS('\nAll verification runs seeded and played.'))
        self.stdout.write('Instructor login for inspection: seed_grader / seed-grader-pass')

    # ---- single-team run ----
    def _run(self, cohort_name, label, decisions, anchor, grade, weeks, grader):
        cohort = Cohort.objects.create(name=cohort_name, tier=Tier.UNDERGRAD)
        cohort.instructors.add(grader)
        student = User.objects.create_user(
            username=f'seed_{label.lower()}_student', password='seed-pass', role=UserRole.STUDENT)
        team = Team.objects.create(cohort=cohort, name=f'Team {label}')
        team.members.add(student)
        run = Run.objects.create(team=team)

        timeline = self._play(run, student, grader, decisions, anchor, grade, weeks)
        run.refresh_from_db()
        self._dump(f'RUN {label}', run, timeline)

    # ---- two-team benchmark run ----
    def _run_d(self, grader):
        cohort = Cohort.objects.create(name='Verification D', tier=Tier.UNDERGRAD)
        cohort.instructors.add(grader)
        teams = {}
        for tlabel, decisions in (('A', RUN_A), ('B', RUN_D_B)):
            student = User.objects.create_user(
                username=f'seed_d{tlabel.lower()}_student', password='seed-pass', role=UserRole.STUDENT)
            team = Team.objects.create(cohort=cohort, name=f'Team {tlabel}')
            team.members.add(student)
            run = Run.objects.create(team=team)
            self._play(run, student, grader, decisions, 'strong', 7, range(1, 12))
            teams[tlabel] = team

        self.stdout.write('\n==================== RUN D (two-team benchmark) ====================')
        for after_week in (8, 11):
            benchmark = Benchmark.objects.get(cohort=cohort, after_week=after_week)
            reveal_benchmark(benchmark)
            factors = benchmark.standings[0]['factors'] if benchmark.standings else []
            self.stdout.write(f'\n  After week {after_week}  (factors: {", ".join(factors)})')
            for row in sorted(benchmark.standings, key=lambda r: r['team_name']):
                self.stdout.write(
                    f"    {row['team_name']:<8} trust_points={row['trust_points']:>3}  "
                    f"total={row['total_score']:>4}  benchmark_score={row['benchmark_score']}")

    # ---- play one run, return per-week timeline snapshots ----
    def _play(self, run, student, grader, decisions, anchor, grade, weeks):
        timeline = []
        for wk in weeks:
            run.refresh_from_db()
            run.current_week = wk
            run.save()
            instance = view_briefing(run)
            payload = {**BUILDERS[wk](), **decisions[wk]}
            submit_week(instance, structured_payload=payload,
                        deliverable_text=f'Seed deliverable, week {wk}.', submitted_by=student)
            instance.refresh_from_db()
            traps = list(instance.score_record.auto_components.get('trap_flags', []))
            finalize_score(instance.score_record,
                           instructor_scores={d: grade for d in SCORE_DIMENSIONS}, graded_by=grader)
            if wk == 1:
                run.refresh_from_db()
                run.state['through_lines']['coherence']['anchor_strength'] = anchor
                run.save()
            run.refresh_from_db()
            g = run.state['gates']
            timeline.append((wk, g['budget_credibility']['state'], g['security_ot']['state'], traps))
        return timeline

    # ---- print a per-run report ----
    def _dump(self, title, run, timeline):
        s = run.state
        self.stdout.write(f'\n==================== {title} ====================')
        self.stdout.write('  week | budget_gate | ot_gate    | trap flags')
        for wk, budget, ot, traps in timeline:
            self.stdout.write(f'   {wk:>2}  | {budget:<11} | {ot:<10} | {", ".join(traps) if traps else "(clean)"}')

        tl = s['through_lines']
        self.stdout.write('\n  through-line endpoints:')
        self.stdout.write(f"    security_ot   posture={tl['security_ot']['posture']} neglect={tl['security_ot']['neglect']}")
        self.stdout.write(f"    cloud_lockin  state={tl['cloud_lockin']['state']} depth={tl['cloud_lockin']['depth']}")
        self.stdout.write(f"    data_rights   posture={tl['data_rights']['posture']}")
        self.stdout.write(f"    coherence     drift_events={len(tl['coherence']['drift_events'])} anchor_strength={tl['coherence']['anchor_strength']}")

        f = s['flags']
        keys = ['board_verdict', 'arc_coherence_settled', 'data_advantage', 'trust_state',
                'infra_sustainable', 'lockin_lesson', 'endgame_tier']
        self.stdout.write('\n  end-state flags: ' + ', '.join(f'{k}={f.get(k)}' for k in keys))

        acc = s['accumulated_scores']
        total = sum(acc.values())
        self.stdout.write(
            f"\n  tier_outcome = {run.tier_outcome}   total = {total}   "
            f"(SJ {acc['strategic_judgment']}, EC {acc['execution_consequence']}, "
            f"COH {acc['coherence']}, DQ {acc['deliverable_quality']})")
