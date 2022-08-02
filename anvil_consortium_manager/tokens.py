from django.contrib.auth.tokens import PasswordResetTokenGenerator

class AccountLinkVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            str(user.pk) + str(timestamp)
        )

account_verification_token = AccountLinkVerificationTokenGenerator()