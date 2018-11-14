from django.contrib import admin
from django.contrib.auth.models import User
from django import forms
from .models import Order

admin.site.register(Order)