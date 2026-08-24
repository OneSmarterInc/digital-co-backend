"""Sign in with a username or an email address.

Students are created with their email as their username, so both already worked
for them. Staff accounts are not — `vikram` has the email
`vikram@vikramsethi.com`, and typing the address returned "no active account
found", which reads as a wrong password rather than the wrong field.

Username is matched first and exactly, preserving Django's existing behaviour:
if one person's email happens to be another person's username, the username
owner keeps their login. Email is the fallback, matched case-insensitively
because nobody capitalises their address consistently.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        user = UserModel._default_manager.filter(username=username).first()

        if user is None and '@' in username:
            matches = list(UserModel._default_manager.filter(email__iexact=username)[:2])
            # Two accounts on one address is ambiguous, and picking either would
            # be a guess about who is signing in. Email is not unique in this
            # schema, so this has to be handled rather than assumed away.
            if len(matches) == 1:
                user = matches[0]

        if user is None:
            # Same timing as a real check, so a failed login cannot be used to
            # find out which addresses have accounts.
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
