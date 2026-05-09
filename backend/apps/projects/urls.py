from django.urls import path

from apps.projects.views import (
    ProjectCollaboratorDeleteView,
    ProjectCollaboratorListCreateView,
    ProjectDetailView,
    ProjectListCreateView,
    ProjectRevisionCommentListCreateView,
    ProjectRevisionDetailView,
    ProjectRevisionListCreateView,
    SharedProjectDetailView,
)

app_name = "projects"

urlpatterns = [
    path("", ProjectListCreateView.as_view(), name="list-create"),
    path("shared/<uuid:share_token>/", SharedProjectDetailView.as_view(), name="shared-detail"),
    path("<int:project_id>/", ProjectDetailView.as_view(), name="detail"),
    path("<int:project_id>/collaborators/", ProjectCollaboratorListCreateView.as_view(), name="collaborators"),
    path("<int:project_id>/collaborators/<int:user_id>/", ProjectCollaboratorDeleteView.as_view(), name="collaborator-delete"),
    path("<int:project_id>/revisions/", ProjectRevisionListCreateView.as_view(), name="revisions"),
    path("<int:project_id>/revisions/<int:revision_id>/", ProjectRevisionDetailView.as_view(), name="revision-detail"),
    path("<int:project_id>/revisions/<int:revision_id>/comments/", ProjectRevisionCommentListCreateView.as_view(), name="revision-comments"),
]
