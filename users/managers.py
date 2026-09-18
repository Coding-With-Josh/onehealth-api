from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Manager for CustomUser.

    WHY THIS FILE EXISTS:
    Django's default User model uses `username` as the login field.
    We're using `email` instead (patients and hospital staff both log in
    with email, never a username). Whenever you swap the login field,
    Django REQUIRES you to write your own manager with create_user() and
    create_superuser() — this is that manager.

    Do not remove this even if it looks like boilerplate — the app will
    not start without it once AUTH_USER_MODEL points at CustomUser.
    """

    def _validate_email(self, email):
        if not email:
            raise ValueError("An email address is required.")
        return self.normalize_email(email)

    def create_user(self, email, password=None, user_type=None, **extra_fields):
        """
        Standard user creation. `user_type` MUST be passed explicitly by
        whichever serializer/view calls this — we deliberately do not
        default it, so nobody accidentally creates an ambiguous account.
        """
        if not user_type:
            raise ValueError("user_type is required (patient / hospital_staff / platform_admin).")

        email = self._validate_email(email)
        user = self.model(email=email, user_type=user_type, **extra_fields)
        user.set_password(password)  # never store raw passwords
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Used only for `python manage.py createsuperuser` (platform admins /
        Django admin access). Forces is_staff/is_superuser True and locks
        user_type to PLATFORM_ADMIN regardless of what's passed in.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # Local import avoids a circular import between models.py and managers.py
        from .models import User

        return self.create_user(
            email=email,
            password=password,
            user_type=User.UserType.PLATFORM_ADMIN,
            **extra_fields,
        )
