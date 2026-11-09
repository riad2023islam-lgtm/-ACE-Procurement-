from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Profile
from .permissions import role_required
from .serializers import CreateUserSerializer, LoginSerializer, RegisterSerializer, user_payload


def _auth_response(user, http_status=status.HTTP_200_OK):
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": user_payload(user)}, status=http_status)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return _auth_response(user, status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        # One generic message so the API does not reveal which usernames exist.
        if user is None or not hasattr(user, "profile"):
            raise AuthenticationFailed("Invalid username or password.")
        return _auth_response(user)


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(user_payload(request.user))


class UserListCreateView(APIView):
    """Admin-only: list and create accounts inside the admin's own organization."""
    permission_classes = [role_required(Profile.ROLE_ADMIN)]

    def get(self, request):
        org = request.user.profile.organization
        profiles = Profile.objects.filter(organization=org).select_related("user")
        return Response([
            {"id": p.user_id, "username": p.user.username, "email": p.user.email, "role": p.role}
            for p in profiles
        ])

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"id": user.id, "username": user.username, "email": user.email,
             "role": user.profile.role},
            status=status.HTTP_201_CREATED,
        )
