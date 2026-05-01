from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.text import slugify


class CustomUserManager(BaseUserManager):
    def _unique_username(self, seed: str) -> str:
        base = slugify(seed)[:140] or "user"
        candidate = base
        suffix = 1
        while self.model.objects.filter(username=candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate[:150]

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The email field must be set")
        email = self.normalize_email(email)
        username = extra_fields.pop("username", None) or self._unique_username(email.split("@")[0])
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("username", self._unique_username(email.split("@")[0]))
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    organisation = models.CharField(max_length=200, blank=True)
    preferred_region = models.CharField(max_length=100, default="india_mumbai")
    preferred_unit = models.CharField(
        max_length=20,
        choices=[("metric", "Metric"), ("imperial", "Imperial")],
        default="metric",
    )
    vastu_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = CustomUserManager()

    def __str__(self):
        return self.email or self.username
