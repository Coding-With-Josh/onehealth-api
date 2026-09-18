from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings

schema_view = get_schema_view(
   openapi.Info(
      title="One health API",
      default_version='v1',
      description="Below, you will find all endpoints and documentation to each of these endpoints",
      contact=openapi.Contact(email="adesolaayodeji53@gmail.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   url=settings.SWAGGER_DOCS_BASE_URL,
   authentication_classes=[],  # optional
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # --- Auth module ---
    path("api/v1/auth/", include("users.urls")),
    path("api/v1/", include("records.urls")),
    path("api/v1/", include("visits.urls")),
    path("api/v1/", include("access.urls")),
    path("api/v1/", include("audit.urls")),
    path("api/v1/", include("cards.urls")),

     # swagger UI
   path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]