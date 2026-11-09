from django.contrib.auth.models import User
from django.db import models


class Organization(models.Model):
    """SRS FR1. org_type is stored so other organization types can be added later."""
    TYPE_EDUCATIONAL = "educational"
    TYPE_CHOICES = [(TYPE_EDUCATIONAL, "Educational institution")]

    name = models.CharField(max_length=120, unique=True)
    org_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_EDUCATIONAL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Profile(models.Model):
    """Links a Django user to one organization and one role (SRS FR2, NFR3, NFR4)."""
    ROLE_ADMIN = "admin"
    ROLE_MANAGER = "manager"
    ROLE_STORE = "store_officer"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Administrator"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_STORE, "Store Officer"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.role}) @ {self.organization.name}"
