from django.db import models
from django.conf import settings  # Import settings for AUTH_USER_MODEL
from django.contrib.auth.models import AbstractUser
import json
import numpy as np

# Custom User model
class User(AbstractUser):
    is_admin = models.BooleanField(default=False)
    is_user = models.BooleanField(default=False)

    class Meta:
        swappable = 'AUTH_USER_MODEL'

# Create your models here.
class UploadedImage(models.Model):
    image = models.ImageField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)