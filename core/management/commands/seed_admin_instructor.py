"""Create or update admin and instructor accounts.

Usage:
    python manage.py seed_admin_instructor
    python manage.py seed_admin_instructor --admin-username admin --admin-password secret123 --instructor-username instructor --instructor-password secret456
"""
from django.core.management.base import BaseCommand

from core.models import User, UserRole


class Command(BaseCommand):
    help = "Create or update admin and instructor accounts."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="vikram")
        parser.add_argument("--admin-password", default="secret123")
        parser.add_argument("--admin-email", default="admin@example.com")
        parser.add_argument("--instructor-username", default="john")
        parser.add_argument("--instructor-password", default="secret123")
        parser.add_argument("--instructor-email", default="instructor@example.com")

    def handle(self, *args, **opts):
        # Create/Update Admin
        admin_user, admin_created = User.objects.get_or_create(
            username=opts["admin_username"],
            defaults={"role": UserRole.ADMIN, "is_staff": True, "is_superuser": True},
        )
        admin_user.role = UserRole.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.email = opts["admin_email"]
        admin_user.set_password(opts["admin_password"])
        admin_user.save()

        admin_verb = "created" if admin_created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Admin {admin_verb}: {admin_user.username}"))
        self.stdout.write(f"  password : {opts['admin_password']}")
        self.stdout.write(f"  email    : {opts['admin_email']}")

        # Create/Update Instructor
        instructor_user, instructor_created = User.objects.get_or_create(
            username=opts["instructor_username"],
            defaults={"role": UserRole.INSTRUCTOR},
        )
        instructor_user.role = UserRole.INSTRUCTOR
        instructor_user.email = opts["instructor_email"]
        instructor_user.set_password(opts["instructor_password"])
        instructor_user.save()

        instructor_verb = "created" if instructor_created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Instructor {instructor_verb}: {instructor_user.username}"))
        self.stdout.write(f"  password : {opts['instructor_password']}")
        self.stdout.write(f"  email    : {opts['instructor_email']}")
