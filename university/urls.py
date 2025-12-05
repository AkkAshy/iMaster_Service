from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'universities', views.UniversityViewSet, basename='university')
router.register(r'buildings', views.BuildingViewSet, basename='building')
router.register(r'floors', views.FloorViewSet, basename='floor')
router.register(r'faculties', views.FacultyViewSet, basename='faculty')
router.register(r'rooms', views.RoomViewSet, basename='room')
router.register(r'warehouses', views.WarehouseViewSet, basename='warehouse')

urlpatterns = [
    path('', include(router.urls)),
]
