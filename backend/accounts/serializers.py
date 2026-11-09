from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Organization, Profile


def _check_password(password, user):
    """Run Django's configured password validators and report all failures."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)})


class RegisterSerializer(serializers.Serializer):
    """Registers a new organization together with its first (admin) user. SRS FR1."""
    organization_name = serializers.CharField(min_length=3, max_length=120)
    username = serializers.CharField(min_length=3, max_length=150, validators=[UnicodeUsernameValidator()])
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    def validate_organization_name(self, value):
        value = " ".join(value.split())
        if Organization.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("This organization is already registered.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        _check_password(attrs["password"], User(username=attrs["username"], email=attrs["email"]))
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        org = Organization.objects.create(name=validated_data["organization_name"])
        user = User.objects.create_user(      # create_user hashes the password
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        Profile.objects.create(user=user, organization=org, role=Profile.ROLE_ADMIN)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class CreateUserSerializer(serializers.Serializer):
    """Lets an organization admin add manager / store officer accounts. SRS FR2."""
    username = serializers.CharField(min_length=3, max_length=150, validators=[UnicodeUsernameValidator()])
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=[Profile.ROLE_MANAGER, Profile.ROLE_STORE])

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        _check_password(attrs["password"], User(username=attrs["username"], email=attrs["email"]))
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        Profile.objects.create(
            user=user,
            organization=self.context["request"].user.profile.organization,
            role=validated_data["role"],
        )
        return user


def user_payload(user):
    profile = user.profile
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": profile.role,
        "organization": {
            "id": profile.organization_id,
            "name": profile.organization.name,
            "type": profile.organization.org_type,
        },
    }
