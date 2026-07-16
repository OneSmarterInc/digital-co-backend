from django.urls import path

from . import views

app_name = 'web'

urlpatterns = [
    path('', views.student_briefing, name='student_briefing'),
    path('advisor/<int:advisor_id>/', views.advisor_consultation, name='advisor_consultation'),
    path('submit/', views.submit_decision, name='submit_decision'),
    path('instructor/score/<int:score_id>/', views.instructor_score, name='instructor_score'),
    path('benchmarks/<int:cohort_id>/<int:after_week>/', views.benchmark_view, name='benchmark'),
]
