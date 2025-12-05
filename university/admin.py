from django.contrib import admin
from .models import University, Building, Faculty, Floor, Room, RoomHistory, FacultyHistory


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')
    search_fields = ('name',)
    list_per_page = 20



@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "university", "address")
    search_fields = ("name", "address",)
    list_filter = ("university",)


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'building')
    list_filter = ('building',)
    search_fields = ('name',)
    list_per_page = 20


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('number', 'building', 'description')
    list_filter = ('building',)
    search_fields = ('description',)
    list_per_page = 20





@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    readonly_fields = ('qr_code_preview',)
    list_display = ("number", "name", "building", "floor", "is_special", "uid")
    list_filter = ("building", "floor", "is_special")
    fields = ('building', 'floor', 'number', 'name', 'is_special', 'photo', 'qr_code_preview')
    search_fields = ("number", "name") # Добавлено для автокомплита
    autocomplete_fields = ["building", "floor"]
    def qr_code_preview(self, obj):
        if obj.qr_code:
            return f'<img src="{obj.qr_code.url}" width="150" height="150" />'
        return "(QR-код не сгенерирован)"
    qr_code_preview.short_description = "QR-код"
    qr_code_preview.allow_tags = True



@admin.register(RoomHistory)
class RoomHistoryAdmin(admin.ModelAdmin):
    list_display = ('room', 'action', 'timestamp')
    list_filter = ('action',)
    search_fields = ('room__number', 'action')
    readonly_fields = ('timestamp',)
    list_per_page = 20

@admin.register(FacultyHistory)
class FacultyHistoryAdmin(admin.ModelAdmin):
    list_display = ('faculty', 'action', 'timestamp')
    list_filter = ('action',)
    search_fields = ('faculty__name', 'action')
    readonly_fields = ('timestamp',)
    list_per_page = 20