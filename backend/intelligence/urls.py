from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view()),
    path("forecast/", views.ForecastView.as_view()),
    path("recommendations/", views.RecommendationListView.as_view()),
]
