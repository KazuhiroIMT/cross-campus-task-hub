from django.urls import path
from . import views

urlpatterns = [
    path('department/boss/', views.department_boss, name='department_boss_my'),
    path('department/<int:dept_id>/boss/', views.department_boss, name='department_boss'),
    path('department/<int:dept_id>/set-title/', views.set_department_title, name='set_department_title'),
    path('island/', views.my_island, name='my_island'),
    path('island/gacha/', views.gacha_page, name='gacha_page'),
    path('achievements/', views.achievements_page, name='achievements_page'),
    path('achievements/set-title/', views.set_current_title, name='set_current_title'),
    path('select-companion/', views.select_companion, name='select_companion'),
    path('graduate-companion/', views.graduate_companion, name='graduate_companion'),
    path('', views.dashboard, name='dashboard'),
    path('task/<int:pk>/update/', views.update_task_status, name='update_task_status'),
    path('task/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/closed/', views.closed_task_list, name='closed_tasks'),
    path('tasks/sent/', views.my_created_tasks, name='my_created_tasks'),
    path('api/students/search/', views.api_search_students, name='api_search_students'),
    path('tasks/other/', views.other_department_tasks, name='other_department_tasks'),
    path('export/json/', views.export_data_json, name='export_data_json'),
    path('export/csv/', views.export_data_csv, name='export_data_csv'),
]