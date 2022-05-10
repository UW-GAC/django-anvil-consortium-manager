#!/usr/bin/env python
import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    try:
        settings_module = os.environ["DJANGO_SETTINGS_MODULE"]
    except KeyError:
        settings_module = "anvil_consortium_manager.tests.settings.test"
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    print("Running with settings " + settings_module)
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["anvil_consortium_manager/tests"])
    sys.exit(bool(failures))
