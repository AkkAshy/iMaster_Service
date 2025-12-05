from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EquipmentTypeViewSet, ContractDocumentViewSet, EquipmentViewSet,
    EquipmentSpecificationViewSet, MovementHistoryViewSet,
    RepairViewSet, DisposalViewSet,
    ContractTemplateViewSet, INNTemplateViewSet,
    BulkEquipmentCreateView, BulkEquipmentInnUpdateView
)
from .static_views import EquipmentStatisticsView, DashboardView

router = DefaultRouter()

# Основные роуты
router.register(r'types', EquipmentTypeViewSet, basename='equipment-type')
router.register(r'specifications', EquipmentSpecificationViewSet, basename='specification')
router.register(r'equipment', EquipmentViewSet, basename='equipment')
router.register(r'movements', MovementHistoryViewSet, basename='movement')
router.register(r'repairs', RepairViewSet, basename='repair')
router.register(r'disposals', DisposalViewSet, basename='disposal')
router.register(r'contracts', ContractDocumentViewSet, basename='contract')
router.register(r'contract-templates', ContractTemplateViewSet, basename='contract-template')
router.register(r'inn-templates', INNTemplateViewSet, basename='inn-template')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # Bulk операции
    path('equipment/bulk-create/', BulkEquipmentCreateView.as_view(), name='equipment-bulk-create'),
    path('equipment/bulk-inn-update/', BulkEquipmentInnUpdateView.as_view(), name='equipment-bulk-inn-update'),

    # Статистика
    path('statistics/', EquipmentStatisticsView.as_view(), name='statistics'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]
