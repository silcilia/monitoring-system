# services/authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class SafeJWTAuthentication(BaseAuthentication):
    """
    Custom JWT Authentication yang tidak menggunakan Session
    """
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return None
        
        try:
            # Extract token from "Bearer <token>"
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return None
            
            token = parts[1]
            access_token = AccessToken(token)
            user_id = access_token.payload.get('user_id')
            user = User.objects.get(id=user_id)
            
            return (user, None)
            
        except (InvalidToken, TokenError, User.DoesNotExist):
            raise AuthenticationFailed('Invalid token')
        
        return None