from django.urls import re_path
from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.views import APIView
try:
    from rest_framework_oauth.authentication import OAuth2Authentication
except ImportError:
    try:
        from rest_framework.authentication import OAuth2Authentication
    except ImportError:
        OAuth2Authentication = None

from rest_framework_jwt import views
from rest_framework_jwt.authentication import JSONWebTokenAuthentication


class MockView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return HttpResponse('mockview-get')

    def post(self, request):
        return HttpResponse('mockview-post')


urlpatterns = [
    re_path(r'^auth-token/$', views.obtain_jwt_token),
    re_path(r'^auth-token-refresh/$', views.refresh_jwt_token),
    re_path(r'^auth-token-verify/$', views.verify_jwt_token),

    re_path(r'^jwt/$', MockView.as_view(
        authentication_classes=[JSONWebTokenAuthentication])),
    re_path(r'^jwt-oauth2/$', MockView.as_view(
        authentication_classes=[
            JSONWebTokenAuthentication, OAuth2Authentication])),
    re_path(r'^oauth2-jwt/$', MockView.as_view(
        authentication_classes=[
            OAuth2Authentication, JSONWebTokenAuthentication])),
]
