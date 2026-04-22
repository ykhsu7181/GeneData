from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.test_api, name='integrations_test'),
    path('rgi/ogigraph/<path:ogi_id>/', views.rgi_ogigraph_view, name='rgi_ogigraph'),
]