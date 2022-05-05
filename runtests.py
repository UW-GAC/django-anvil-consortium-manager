#!/usr/bin/env python
import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    os.environ[
        "DJANGO_SETTINGS_MODULE"
    ] = "anvil_consortium_manager.tests.settings.test"
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["anvil_consortium_manager/tests"])
    sys.exit(bool(failures))
