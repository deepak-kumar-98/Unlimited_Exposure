# apps/content/urls.py

from django.urls import path
from .views import IngestContentAPIView

urlpatterns = [
    path("ingest/", IngestContentAPIView.as_view(), name="ingest-content"),
]