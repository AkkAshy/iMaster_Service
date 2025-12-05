from django.contrib import admin
from .models import (
    Equipment, EquipmentType, EquipmentSpecification,
    MovementHistory, ContractDocument, ContractTemplate, INNTemplate,
    Repair, Disposal
)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'type', 'status', 'room', 'warehouse', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'inn')
    list_filter = ('is_active', 'status', 'type', 'warehouse')
    readonly_fields = ('uid', 'qr_code', 'specs', 'created_at')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(EquipmentType)
class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(EquipmentSpecification)
class EquipmentSpecificationAdmin(admin.ModelAdmin):
    list_display = ('type', 'author', 'created_at')
    search_fields = ('type__name',)
    list_filter = ('author',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MovementHistory)
class MovementHistoryAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'from_room', 'to_room', 'moved_at')
    list_filter = ('moved_at',)
    search_fields = ('equipment__name',)
    readonly_fields = ('moved_at',)


@admin.register(ContractDocument)
class ContractDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'file', 'created_at')
    search_fields = ('number',)
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(INNTemplate)
class INNTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Repair)
class RepairAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'status', 'start_date', 'end_date', 'original_room')
    list_filter = ('status', 'start_date')
    search_fields = ('equipment__name', 'notes')


@admin.register(Disposal)
class DisposalAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'disposal_date', 'reason', 'original_room')
    list_filter = ('disposal_date',)
    search_fields = ('equipment__name', 'reason')
