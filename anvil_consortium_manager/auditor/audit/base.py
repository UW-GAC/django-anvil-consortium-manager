from abc import ABC

import django_tables2 as tables
from django.utils import timezone


# Audit classes for individual model instances:
class ModelInstanceResult:
    """Class to hold an audit result for a specific instance of a model."""

    def __init__(self, model_instance):
        self.model_instance = model_instance
        self.errors = set()

    def __eq__(self, other):
        return self.model_instance == other.model_instance and self.errors == other.errors

    def __str__(self):
        return str(self.model_instance)

    def add_error(self, error):
        """Add an error to the audit result for this model instance."""
        self.errors.add(error)

    def ok(self):
        """Check whether an audit result has errors."""

        if self.errors:
            return False
        else:
            return True


class NotInAppResult:
    """Class to hold an audit result for a record that is not present in the app."""

    def __init__(self, record):
        self.record = record

    def __str__(self):
        return self.record

    def __eq__(self, other):
        return self.record == other.record


class IgnoredResult:
    """Class to hold an audit result for a specific record in an Ignore table."""

    def __init__(self, model_instance, record=None):
        self.record = record
        self.model_instance = model_instance

    def __eq__(self, other):
        return self.model_instance == other.model_instance and self.record == other.record

    def __str__(self):
        return str(self.record)


# Tables for reporting audit results:
class VerifiedTable(tables.Table):
    """Table for verified results."""

    model_instance = tables.columns.Column(linkify=True, orderable=False)


# Tables for reporting audit results:
class ErrorTable(tables.Table):
    """Table for results with errors."""

    model_instance = tables.columns.Column(linkify=True, orderable=False)
    errors = tables.columns.Column(orderable=False)

    def render_errors(self, record):
        return ", ".join(sorted(record.errors))


class NotInAppTable(tables.Table):
    record = tables.columns.Column(orderable=False, empty_values=())


class IgnoredTable(tables.Table):
    model_instance = tables.columns.Column(orderable=False, verbose_name="Details")
    record = tables.columns.Column(orderable=False)

    def render_model_instance(self, record):
        return "See details"


# Audit classes for object classes:
class AnVILAudit(ABC):
    """Abstract base class for AnVIL audit results."""

    verified_table_class = VerifiedTable
    error_table_class = ErrorTable
    not_in_app_table_class = NotInAppTable
    ignored_table_class = IgnoredTable
    cache_key = None

    def __init__(self):
        self._model_instance_results = []
        self._not_in_app_results = []
        self._ignored_results = []
        self.timestamp = timezone.now()

    def get_cache_key(self):
        if not self.cache_key:
            raise NotImplementedError(
                "%(cls)s is missing a cache key. Define %(cls)s.cache_name or override "
                "%(cls)s.get_cache_key()." % {"cls": self.__class__.__name__}
            )
        return self.cache_key

    def ok(self):
        model_instances_ok = all([x.ok() for x in self._model_instance_results])
        not_in_app_ok = len(self._not_in_app_results) == 0
        return model_instances_ok and not_in_app_ok

    def run_audit(self):
        raise NotImplementedError("Define a run_audit method.")

    def add_result(self, result):
        if isinstance(result, NotInAppResult):
            self._add_not_in_app_result(result)
        elif isinstance(result, IgnoredResult):
            self._add_ignored_result(result)
        elif isinstance(result, ModelInstanceResult):
            self._add_model_instance_result(result)
        else:
            raise ValueError("result must be ModelInstanceResult, NotInAppResult or IgnoredResult.")

    def _add_not_in_app_result(self, result):
        # Check that it hasn't been added yet.
        check = [x for x in self._not_in_app_results if x == result]
        if len(check) > 0:
            raise ValueError("Already added a result for {}.".format(result.record))
        self._not_in_app_results.append(result)

    def _add_model_instance_result(self, result):
        check = [x for x in self._model_instance_results if x.model_instance == result.model_instance]
        if len(check) > 0:
            raise ValueError("Already added a result for {}.".format(result.model_instance))
        self._model_instance_results.append(result)

    def _add_ignored_result(self, result):
        check = [x for x in self._ignored_results if x.model_instance == result.model_instance]
        if len(check) > 0:
            raise ValueError("Already added a result for {}.".format(result.model_instance))
        self._ignored_results.append(result)

    def get_result_for_model_instance(self, model_instance):
        results = [x for x in self._model_instance_results if x.model_instance == model_instance]
        if len(results) != 1:
            raise ValueError("model_instance is not in the results.")
        return results[0]

    def get_verified_results(self):
        return [x for x in self._model_instance_results if x.ok()]

    def get_error_results(self):
        return [x for x in self._model_instance_results if not x.ok()]

    def get_ignored_results(self):
        return self._ignored_results

    def get_not_in_app_results(self):
        return self._not_in_app_results

    def get_verified_table(self):
        return self.verified_table_class(self.get_verified_results())

    def get_error_table(self):
        return self.error_table_class(self.get_error_results())

    def get_not_in_app_table(self):
        return self.not_in_app_table_class(self.get_not_in_app_results())

    def get_ignored_table(self):
        return self.ignored_table_class(self.get_ignored_results())

    def export(
        self,
        include_verified=True,
        include_errors=True,
        include_not_in_app=True,
        include_ignored=True,
    ):
        """Return a dictionary representation of the audit results."""
        exported_results = {}
        if include_verified:
            exported_results["verified"] = [
                {"id": result.model_instance.pk, "instance": result.model_instance}
                for result in self.get_verified_results()
            ]
        if include_errors:
            exported_results["errors"] = [
                {
                    "id": result.model_instance.pk,
                    "instance": result.model_instance,
                    "errors": list(result.errors),
                }
                for result in self.get_error_results()
            ]
        if include_not_in_app:
            exported_results["not_in_app"] = list(sorted([x.record for x in self.get_not_in_app_results()]))
        if include_ignored:
            exported_results["ignored"] = [
                {"id": result.model_instance.pk, "instance": result.model_instance, "record": result.record}
                for result in self.get_ignored_results()
            ]
        return exported_results
