from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountLinkVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, email_entry, timestamp):
        return str(email_entry.pk) + str(timestamp) + str(email_entry.email)


account_verification_token = AccountLinkVerificationTokenGenerator()
