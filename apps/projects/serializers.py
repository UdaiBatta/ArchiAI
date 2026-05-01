from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.html import strip_tags
from rest_framework import serializers

from apps.design.serializers import DesignResponseSerializer, DesignListSerializer
from apps.projects.models import Comment, DesignRevision, Project, ProjectCollaborator


User = get_user_model()


def validate_plain_text(value: str) -> str:
    value = value or ""
    if strip_tags(value) != value:
        raise serializers.ValidationError("HTML is not allowed.")
    return value.strip()


class CollaboratorUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "preferred_region", "preferred_unit", "vastu_enabled"]


class ProjectCollaboratorSerializer(serializers.ModelSerializer):
    user = CollaboratorUserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = ProjectCollaborator
        fields = ["id", "user", "user_id", "email", "role", "invited_at"]
        read_only_fields = ["id", "user", "invited_at"]


class ProjectListSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    collaborator_count = serializers.IntegerField(read_only=True)
    revision_count = serializers.IntegerField(read_only=True)
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "description",
            "region",
            "building_type",
            "status",
            "is_public",
            "share_token",
            "share_url",
            "owner_email",
            "collaborator_count",
            "revision_count",
            "thumbnail",
            "created_at",
            "updated_at",
        ]

    def get_share_url(self, obj):
        return f"{settings.FRONTEND_URL}/shared/{obj.share_token}"


class ProjectDetailSerializer(ProjectListSerializer):
    owner = CollaboratorUserSerializer(read_only=True)
    collaborators = ProjectCollaboratorSerializer(many=True, read_only=True)
    latest_revision = serializers.SerializerMethodField()

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + ["owner", "collaborators", "latest_revision"]

    def get_latest_revision(self, obj):
        revision = obj.revisions.order_by("-version_number", "-created_at").first()
        if not revision:
            return None
        return DesignRevisionSummarySerializer(revision, context=self.context).data


class ProjectCreateUpdateSerializer(serializers.ModelSerializer):
    title = serializers.CharField(validators=[validate_plain_text])
    description = serializers.CharField(required=False, allow_blank=True, validators=[validate_plain_text])
    region = serializers.CharField(validators=[validate_plain_text])
    building_type = serializers.CharField(validators=[validate_plain_text])

    class Meta:
        model = Project
        fields = ["title", "description", "region", "building_type", "status", "is_public"]
        extra_kwargs = {"status": {"required": False}, "is_public": {"required": False}}


class DesignRevisionSummarySerializer(serializers.ModelSerializer):
    session = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = DesignRevision
        fields = [
            "id",
            "project",
            "session",
            "version_number",
            "label",
            "is_pinned",
            "created_by",
            "created_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "project", "session", "version_number", "created_by", "created_by_email", "created_at"]

    def get_session(self, obj):
        return DesignListSerializer(obj.session, context=self.context).data


class DesignRevisionDetailSerializer(DesignRevisionSummarySerializer):
    session = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta(DesignRevisionSummarySerializer.Meta):
        fields = DesignRevisionSummarySerializer.Meta.fields + ["comments"]

    def get_session(self, obj):
        return DesignResponseSerializer(obj.session, context=self.context).data

    def get_comments(self, obj):
        return CommentSerializer(obj.comments.select_related("author").all(), many=True, context=self.context).data


class DesignRevisionCreateSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    label = serializers.CharField(required=False, allow_blank=True, validators=[validate_plain_text])
    is_pinned = serializers.BooleanField(required=False, default=False)


class CommentSerializer(serializers.ModelSerializer):
    author = CollaboratorUserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "revision", "author", "body", "zone_ref", "created_at", "updated_at"]
        read_only_fields = ["id", "revision", "author", "created_at", "updated_at"]


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(validators=[validate_plain_text])
    zone_ref = serializers.CharField(required=False, allow_blank=True, validators=[validate_plain_text])
