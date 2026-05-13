from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CobraUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Cobra", {"fields": ("role", "phone_number", "profile_photo", "is_active_on_duty", "fcm_token")}),
    )
    list_display = ("username", "email", "role", "is_staff", "is_active_on_duty")
