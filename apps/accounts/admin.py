from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "username", "is_staff", "is_active", "created_at")
    list_filter = ("is_staff", "is_superuser", "is_active", "preferred_region", "vastu_enabled")
    fieldsets = UserAdmin.fieldsets + (("ArchiAI", {"fields": ("avatar", "organisation", "preferred_region", "preferred_unit", "vastu_enabled", "created_at")}),)
    readonly_fields = ("created_at",)
    add_fieldsets = UserAdmin.add_fieldsets + (("ArchiAI", {"fields": ("email", "organisation", "preferred_region", "preferred_unit", "vastu_enabled")}),)
    search_fields = ("email", "username", "first_name", "last_name", "organisation")
    ordering = ("email",)
