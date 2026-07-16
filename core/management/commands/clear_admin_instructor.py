"""Delete all admin and instructor accounts from the database.

Usage:
    python manage.py clear_admin_instructor
    python manage.py clear_admin_instructor --confirm (to skip confirmation prompt)
"""
from django.core.management.base import BaseCommand

from core.models import User, UserRole


class Command(BaseCommand):
    help = "Delete all admin and instructor accounts from the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Skip confirmation prompt and delete immediately.",
        )

    def handle(self, *args, **opts):
        # Count users to be deleted
        admin_count = User.objects.filter(role=UserRole.ADMIN).count()
        instructor_count = User.objects.filter(role=UserRole.INSTRUCTOR).count()
        total_count = admin_count + instructor_count

        if total_count == 0:
            self.stdout.write(self.style.WARNING("No admin or instructor accounts to delete."))
            return

        # Show what will be deleted
        self.stdout.write(
            self.style.WARNING(
                f"About to delete {admin_count} admin(s) and {instructor_count} instructor(s)."
            )
        )

        # Ask for confirmation if not provided
        if not opts["confirm"]:
            confirm = input("Are you sure you want to delete all admin and instructor accounts? (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        # Delete admins
        deleted_admins, _ = User.objects.filter(role=UserRole.ADMIN).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {admin_count} admin account(s)."))

        # Delete instructors
        deleted_instructors, _ = User.objects.filter(role=UserRole.INSTRUCTOR).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {instructor_count} instructor account(s)."))

        self.stdout.write(
            self.style.SUCCESS(f"✓ Cleared {total_count} admin/instructor account(s) from the database.")
        )
