"""Create a viewable DigitalCo run in one step.

This automates Section 4 of the deployment runbook (cohort -> student ->
team -> run) plus an instructor login, so a fresh database goes from
`migrate` to a clickable run without manual admin work. It is idempotent:
re-running updates passwords and roles but does not create duplicates.

Usage:
    python manage.py bootstrap_demo
    python manage.py bootstrap_demo --tier GRADUATE
    python manage.py bootstrap_demo --student-pass secret1 --instructor-pass secret2
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Cohort, Run, RunStatus, Team, Tier, User, UserRole


class Command(BaseCommand):
    help = "Create an instructor, student, cohort, team, and a week-1 run to view."

    def add_arguments(self, parser):
        parser.add_argument("--tier", choices=[Tier.UNDERGRAD, Tier.GRADUATE],
                            default=Tier.UNDERGRAD,
                            help="Cohort tier to seed (default UNDERGRAD).")
        parser.add_argument("--cohort-name", default="Demo Cohort")
        parser.add_argument("--team-name", default="Team Alpha")
        parser.add_argument("--student", default="student1")
        parser.add_argument("--student-pass", default="student-pass-123")
        parser.add_argument("--instructor", default="vikram")
        parser.add_argument("--instructor-pass", default="instructor-pass-123")

    @transaction.atomic
    def handle(self, *args, **opts):
        # Instructor: staff + superuser for admin, role INSTRUCTOR so the
        # web instructor scoring and benchmark screens authorize correctly.
        instructor, _ = User.objects.get_or_create(
            username=opts["instructor"],
            defaults={"role": UserRole.INSTRUCTOR, "is_staff": True, "is_superuser": True},
        )
        instructor.role = UserRole.INSTRUCTOR
        instructor.is_staff = True
        instructor.is_superuser = True
        instructor.set_password(opts["instructor_pass"])
        instructor.save()

        student, _ = User.objects.get_or_create(
            username=opts["student"],
            defaults={"role": UserRole.STUDENT},
        )
        student.role = UserRole.STUDENT
        student.set_password(opts["student_pass"])
        student.save()

        cohort, _ = Cohort.objects.get_or_create(
            name=opts["cohort_name"], defaults={"tier": opts["tier"]},
        )
        cohort.tier = opts["tier"]
        cohort.save()
        cohort.instructors.add(instructor)

        team, _ = Team.objects.get_or_create(cohort=cohort, name=opts["team_name"])
        team.members.add(student)

        run, created = Run.objects.get_or_create(
            team=team,
            defaults={"current_week": 1, "status": RunStatus.IN_PROGRESS},
        )

        self.stdout.write(self.style.SUCCESS("DigitalCo demo run ready."))
        self.stdout.write(f"  cohort      : {cohort.name} ({cohort.tier})")
        self.stdout.write(f"  team        : {team.name}")
        self.stdout.write(f"  run         : week {run.current_week}, {run.status} "
                          f"({'created' if created else 'existing'})")
        self.stdout.write("")
        self.stdout.write(f"  student log-in    : {student.username} / {opts['student_pass']}")
        self.stdout.write(f"  instructor log-in : {instructor.username} / {opts['instructor_pass']}")
        self.stdout.write("")
        self.stdout.write("  Student view : /        (Week 1 briefing)")
        self.stdout.write("  Admin        : /admin/")
