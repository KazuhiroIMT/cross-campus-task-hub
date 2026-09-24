from django.urls import path
from . import views

urlpatterns = [
    path('select-companion/', views.select_companion, name='select_companion'),
    path('', views.dashboard, name='dashboard'),
    path('task/<int:pk>/update/', views.update_task_status, name='update_task_status'),
    path('task/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/closed/', views.closed_task_list, name='closed_tasks'),
    path('tasks/sent/', views.my_created_tasks, name='my_created_tasks'),
    path('api/students/search/', views.api_search_students, name='api_search_students'),
    path('tasks/other/', views.other_department_tasks, name='other_department_tasks'),
]