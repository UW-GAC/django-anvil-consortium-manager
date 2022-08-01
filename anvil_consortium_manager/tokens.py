from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import six

class AccountLinkVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) + six.text_type(timestamp)
        )

account_verification_token = AccountLinkVerificationTokenGenerator()