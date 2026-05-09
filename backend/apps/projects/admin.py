from django.contrib import admin

from apps.projects.models import Comment, DesignRevision, Project, ProjectCollaborator


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "owner", "region", "building_type", "status", "is_public", "updated_at"]
    list_filter = ["status", "is_public", "region", "building_type"]
    search_fields = ["title", "description", "owner__email"]
    readonly_fields = ["share_token", "created_at", "updated_at"]


@admin.register(ProjectCollaborator)
class ProjectCollaboratorAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "user", "role", "invited_at"]
    list_filter = ["role", "invited_at"]
    search_fields = ["project__title", "user__email"]


@admin.register(DesignRevision)
class DesignRevisionAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "version_number", "label", "is_pinned", "created_by", "created_at"]
    list_filter = ["is_pinned", "created_at"]
    search_fields = ["project__title", "label", "session__raw_text"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "revision", "author", "zone_ref", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["body", "zone_ref", "author__email", "revision__project__title"]
