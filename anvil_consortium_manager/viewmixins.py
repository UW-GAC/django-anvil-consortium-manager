import math

import networkx as nx
import numpy as np
import plotly
import plotly.graph_objects as go
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import ContextMixin
from django.views.generic.detail import SingleObjectMixin

from . import models
from .adapters.account import get_account_adapter
from .adapters.managed_group import get_managed_group_adapter
from .adapters.workspace import workspace_adapter_registry
from .audit import base as base_audit


class AnVILAuditMixin:
    """Mixin to display AnVIL audit results."""

    audit_class = None

    def get_audit_instance(self):
        if not self.audit_class:
            raise ImproperlyConfigured(
                "%(cls)s is missing an audit class. Define %(cls)s.audit_class or override "
                "%(cls)s.get_audit_instance()." % {"cls": self.__class__.__name__}
            )
        else:
            return self.audit_class()

    def run_audit(self):
        self.audit_results = self.get_audit_instance()
        self.audit_results.run_audit()

    def get(self, request, *args, **kwargs):
        self.run_audit()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        """Add audit results to the context data."""
        context = super().get_context_data(*args, **kwargs)
        context["audit_timestamp"] = timezone.now()
        context["audit_ok"] = self.audit_results.ok()
        context["verified_table"] = base_audit.VerifiedTable(self.audit_results.get_verified_results())
        context["error_table"] = base_audit.ErrorTable(self.audit_results.get_error_results())
        context["not_in_app_table"] = base_audit.NotInAppTable(self.audit_results.get_not_in_app_results())
        return context


class AccountAdapterMixin:
    """Class for handling account adapters."""

    def get(self, request, *args, **kwargs):
        self.adapter = get_account_adapter()
        return super().get(request, *args, **kwargs)

    def get_filterset_class(self):
        return self.adapter().get_list_filterset_class()
        # return filters.AccountListFilter

    def get_table_class(self):
        return self.adapter().get_list_table_class()


class ManagedGroupAdapterMixin:
    """Mixin to handle managed group adapters."""

    def get(self, request, *args, **kwargs):
        self.adapter = get_managed_group_adapter()()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.adapter = get_managed_group_adapter()()
        return super().post(request, *args, **kwargs)


class ManagedGroupGraphMixin:
    """Mixin to add a plotly graph of group structure to context data."""

    def get_graph(self):
        """Return a graph of the group structure."""
        raise NotImplementedError("You must override get_graph.")

    def layout_graph(self):
        """Lay out the nodes in the graph."""
        # Networkx layout that requires graphviz:
        # self.graph_layout = nx.drawing.nx_agraph.graphviz_layout(self.graph, prog="neato")
        # Networkx layout that requires scipy:
        # self.graph_layout = nx.kamada_kawai_layout(self.graph)
        self.graph_layout = nx.spring_layout(self.graph)

    def plot_graph(self):
        """Create a plotly figure of the graph."""
        point_size = 10

        # Set up the figure.
        layout = go.Layout(
            height=700,
            # showlegend=False,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
        )

        # Create the figure.
        fig = go.Figure(layout=layout)

        if self.graph:
            # Group nodes as points.
            node_x = []
            node_y = []
            node_labels = []
            node_annotations = []
            node_color = []
            for node, d in self.graph.nodes(data=True):
                x, y = self.graph_layout[node]
                node_x.append(x)
                node_y.append(y)
                node_labels.append(
                    node + "<br>Number of groups: {}<br>Number of accounts: {}".format(d["n_groups"], d["n_accounts"])
                )
                node_annotations.append(
                    go.layout.Annotation(
                        dict(
                            x=x,
                            y=y,
                            xref="x",
                            yref="y",
                            text=node,
                            arrowhead=0,
                            arrowcolor="#ccc",
                        )
                    )
                )
                node_color.append(math.log10(max(1, d["n_groups"] + d["n_accounts"])))

            node_trace = go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers",
                hoverinfo="text",
                text=node_labels,
                textposition="top center",
                marker=dict(
                    color=node_color,
                    size=point_size,
                    line_width=2,
                    showscale=True,
                    colorscale="YlGnBu",
                    colorbar=dict(
                        thickness=15,
                        title="Group or account members",
                        xanchor="left",
                        titleside="right",
                        tickmode="array",
                        tickvals=[np.min(node_color), np.max(node_color)],
                        ticktext=["Fewer", "More"],
                        ticks="outside",
                    ),
                ),
                name="managed groups",
            )
            fig.add_trace(node_trace)

            # Group memberships as lines.
            edge_x_member = []
            edge_y_member = []
            edge_x_admin = []
            edge_y_admin = []
            for u, v, e in self.graph.edges(data=True):
                # Ignore direction.
                x1, y1 = self.graph_layout[v]
                x0, y0 = self.graph_layout[u]
                if e["role"] == models.GroupGroupMembership.MEMBER:
                    edge_x = edge_x_member
                    edge_y = edge_y_member
                elif e["role"] == models.GroupGroupMembership.ADMIN:
                    edge_x = edge_x_admin
                    edge_y = edge_y_admin
                    # Reverse order so arrows go from child to parent instead of parent to child.
                edge_x.append(x1)
                edge_x.append(x0)
                edge_x.append(None)
                edge_y.append(y1)
                edge_y.append(y0)
                edge_y.append(None)

            # Member relationships.
            edge_trace_member = go.Scatter(
                name="member role",
                x=edge_x_member,
                y=edge_y_member,
                line=dict(width=0.5, color="#888"),
                hoverinfo="none",
                mode="lines+markers",
                marker=dict(
                    symbol="arrow",
                    size=15,
                    angleref="previous",
                ),
            )
            fig.add_trace(edge_trace_member)

            # Admin relationships.
            edge_trace_admin = go.Scatter(
                x=edge_x_admin,
                y=edge_y_admin,
                line=dict(width=2, color="#888"),
                hoverinfo="none",
                mode="lines+markers",
                marker=dict(
                    symbol="arrow",
                    size=15,
                    angleref="previous",
                ),
                name="admin role",
            )
            fig.add_trace(edge_trace_admin)

            # Add group names as annotations.
            fig.update_layout(
                {"annotations": node_annotations},
                margin=dict(l=20, r=20, t=50, b=20),
                plot_bgcolor="#eee",
            )

        return fig

    def get_context_data(self, **kwargs):
        """Add the graph to the context data."""
        context = super().get_context_data()
        self.get_graph()
        self.layout_graph()
        context["graph"] = plotly.io.to_html(self.plot_graph(), full_html=False)
        return context


class SingleAccountMixin(SingleObjectMixin):
    """Retrieve an account using the uuid field."""

    model = models.Account

    def get_object(self, queryset=None):
        """Return the object the view is displaying."""
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
        # Filter the queryset based on kwargs.
        uuid = self.kwargs.get("uuid", None)
        queryset = queryset.filter(uuid=uuid)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj


class WorkspaceAdapterMixin:
    """Class for handling workspace adapters."""

    def get_workspace_type(self):
        # Try getting it from the kwargs.
        workspace_type = self.kwargs.get("workspace_type")
        return workspace_type

    def get_adapter(self):
        workspace_type = self.get_workspace_type()
        if workspace_type:
            try:
                adapter = workspace_adapter_registry.get_adapter(workspace_type)
            except KeyError:
                raise Http404("workspace_type is not registered.")
        else:
            raise AttributeError("`workspace_type` must be specified.")
        return adapter

    def get(self, request, *args, **kwargs):
        self.adapter = self.get_adapter()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        if "workspace_type_display_name" not in kwargs:
            kwargs["workspace_type_display_name"] = self.adapter.get_name()
        return super().get_context_data(**kwargs)


class RegisteredWorkspaceAdaptersMixin(ContextMixin):
    """Add registered workspaces to the context data."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Instantiate each adapter class for use in the template.
        registered_workspaces = [x() for x in workspace_adapter_registry.get_registered_adapters().values()]
        context["registered_workspace_adapters"] = registered_workspaces
        return context
