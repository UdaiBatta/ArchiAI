from django.db.models import Count, Max, Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.design.models import DesignSession
from apps.projects.models import Comment, DesignRevision, Project, ProjectCollaborator
from apps.projects.serializers import (
    CommentCreateSerializer,
    CommentSerializer,
    DesignRevisionCreateSerializer,
    DesignRevisionDetailSerializer,
    DesignRevisionSummarySerializer,
    ProjectCollaboratorSerializer,
    ProjectCreateUpdateSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
)


def get_accessible_projects_queryset(user):
    return Project.objects.select_related("owner").prefetch_related("collaborators__user", "revisions__session").filter(
        Q(owner=user) | Q(collaborators__user=user)
    ).distinct()


def get_project_for_user(user, project_id):
    return get_accessible_projects_queryset(user).filter(id=project_id).first()


def can_manage_project(user, project):
    if project.owner_id == user.id:
        return True
    return project.collaborators.filter(user=user, role="admin").exists()


def get_public_revision(project):
    return (
        project.revisions.select_related("session", "created_by")
        .prefetch_related("comments__author")
        .filter(is_pinned=True)
        .order_by("-version_number", "-created_at")
        .first()
        or project.revisions.select_related("session", "created_by").prefetch_related("comments__author").order_by(
            "-version_number", "-created_at"
        ).first()
    )


class ProjectListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_accessible_projects_queryset(request.user)

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        building_type = request.query_params.get("building_type")
        if building_type:
            queryset = queryset.filter(building_type__iexact=building_type)

        region = request.query_params.get("region")
        if region:
            queryset = queryset.filter(region__iexact=region)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(title__icontains=search)

        queryset = queryset.annotate(
            collaborator_count=Count("collaborators", distinct=True),
            revision_count=Count("revisions", distinct=True),
        ).order_by("-updated_at")

        page_size = int(request.query_params.get("page_size", 20))
        page = int(request.query_params.get("page", 1))
        start = (page - 1) * page_size
        end = start + page_size
        items = queryset[start:end]

        return Response(
            {
                "count": queryset.count(),
                "page": page,
                "page_size": page_size,
                "results": ProjectListSerializer(items, many=True, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = ProjectCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = Project.objects.create(owner=request.user, **serializer.validated_data)
        return Response(ProjectDetailSerializer(project, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, request, project_id):
        return get_project_for_user(request.user, project_id)

    def get(self, request, project_id):
        project = self.get_object(request, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectDetailSerializer(project, context={"request": request}).data, status=status.HTTP_200_OK)

    def patch(self, request, project_id):
        project = self.get_object(request, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_project(request.user, project):
            return Response({"detail": "You do not have permission to edit this project."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProjectCreateUpdateSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectDetailSerializer(project, context={"request": request}).data, status=status.HTTP_200_OK)

    def delete(self, request, project_id):
        project = self.get_object(request, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_project(request.user, project):
            return Response({"detail": "You do not have permission to archive this project."}, status=status.HTTP_403_FORBIDDEN)
        project.status = "archived"
        project.save(update_fields=["status", "updated_at"])
        return Response(ProjectDetailSerializer(project, context={"request": request}).data, status=status.HTTP_200_OK)


class SharedProjectDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, share_token):
        project = Project.objects.select_related("owner").prefetch_related("collaborators__user", "revisions__session", "revisions__comments__author").filter(
            share_token=share_token,
            is_public=True,
        ).first()
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        revision = get_public_revision(project)
        payload = ProjectDetailSerializer(project, context={"request": request}).data
        payload["active_revision"] = DesignRevisionDetailSerializer(revision, context={"request": request}).data if revision else None
        return Response(payload, status=status.HTTP_200_OK)


class ProjectCollaboratorListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_project(self, request, project_id):
        return get_project_for_user(request.user, project_id)

    def get(self, request, project_id):
        project = self.get_project(request, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectCollaboratorSerializer(project.collaborators.select_related("user").all(), many=True).data, status=status.HTTP_200_OK)

    def post(self, request, project_id):
        project = self.get_project(request, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_project(request.user, project):
            return Response({"detail": "You do not have permission to manage collaborators."}, status=status.HTTP_403_FORBIDDEN)

        email = str(request.data.get("email", "") or "").strip()
        role = str(request.data.get("role", "viewer") or "viewer").strip()
        user = project.owner.__class__.objects.filter(email__iexact=email).first() if email else None
        if not user:
            return Response({"detail": "User with that email was not found."}, status=status.HTTP_404_NOT_FOUND)

        collaborator, created = ProjectCollaborator.objects.update_or_create(
            project=project,
            user=user,
            defaults={"role": role},
        )
        return Response(ProjectCollaboratorSerializer(collaborator).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ProjectCollaboratorDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, project_id, user_id):
        project = get_project_for_user(request.user, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_project(request.user, project):
            return Response({"detail": "You do not have permission to manage collaborators."}, status=status.HTTP_403_FORBIDDEN)

        deleted, _ = ProjectCollaborator.objects.filter(project=project, user_id=user_id).delete()
        if not deleted:
            return Response({"detail": "Collaborator not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectRevisionListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        project = get_project_for_user(request.user, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        revisions = project.revisions.select_related("session", "created_by").prefetch_related("comments__author").order_by("-version_number", "-created_at")
        return Response(DesignRevisionSummarySerializer(revisions, many=True, context={"request": request}).data, status=status.HTTP_200_OK)

    def post(self, request, project_id):
        project = get_project_for_user(request.user, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_project(request.user, project):
            return Response({"detail": "You do not have permission to create revisions."}, status=status.HTTP_403_FORBIDDEN)

        serializer = DesignRevisionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_id = serializer.validated_data["session_id"]
        session = DesignSession.objects.filter(id=session_id).first()
        if not session:
            return Response({"detail": "Design session not found."}, status=status.HTTP_404_NOT_FOUND)
        if DesignRevision.objects.filter(session=session).exists():
            return Response({"detail": "That design session is already linked to a revision."}, status=status.HTTP_400_BAD_REQUEST)

        next_version = (project.revisions.aggregate(max_version=Max("version_number")).get("max_version") or 0) + 1
        revision = DesignRevision.objects.create(
            project=project,
            session=session,
            version_number=next_version,
            label=serializer.validated_data.get("label", ""),
            is_pinned=serializer.validated_data.get("is_pinned", False),
            created_by=request.user,
        )
        return Response(DesignRevisionDetailSerializer(revision, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ProjectRevisionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id, revision_id):
        project = get_project_for_user(request.user, project_id)
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        revision = project.revisions.select_related("session", "created_by").prefetch_related("comments__author").filter(id=revision_id).first()
        if not revision:
            return Response({"detail": "Revision not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DesignRevisionDetailSerializer(revision, context={"request": request}).data, status=status.HTTP_200_OK)


class ProjectRevisionCommentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_revision(self, request, project_id, revision_id):
        project = get_project_for_user(request.user, project_id)
        if not project:
            return None, Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        revision = project.revisions.select_related("session", "created_by").filter(id=revision_id).first()
        if not revision:
            return None, Response({"detail": "Revision not found."}, status=status.HTTP_404_NOT_FOUND)
        return revision, None

    def get(self, request, project_id, revision_id):
        revision, error_response = self.get_revision(request, project_id, revision_id)
        if error_response:
            return error_response
        comments = revision.comments.select_related("author").all()
        return Response(CommentSerializer(comments, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, project_id, revision_id):
        revision, error_response = self.get_revision(request, project_id, revision_id)
        if error_response:
            return error_response
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = Comment.objects.create(
            revision=revision,
            author=request.user,
            body=serializer.validated_data["body"],
            zone_ref=serializer.validated_data.get("zone_ref", ""),
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
