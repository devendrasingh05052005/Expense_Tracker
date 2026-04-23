from django.urls import path
from . import views
from . import streaming_views

urlpatterns = [
    # Auth
    path('register/',  views.register_view,  name='register'),
    path('login/',     views.login_view,     name='login'),
    path('logout/',    views.logout_view,    name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Expenses
    path('expenses/',           views.expense_list,   name='expense_list'),
    path('expenses/add/',       views.expense_add,    name='expense_add'),
    path('expenses/<int:pk>/edit/',   views.expense_edit,   name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),

    # Receipt / OCR
    path('upload/',       views.upload_receipt,      name='upload_receipt'),
    path('save-scanned/', views.save_scanned_expense, name='save_scanned'),

    # Reports
    path('download/csv/', views.download_csv, name='download_csv'),
    path('download/pdf/', views.download_pdf, name='download_pdf'),
    
    # AI Agent
    path('ai-agent/', views.ai_agent, name='ai_agent'),
    path('ai-agent-stream/', streaming_views.ai_agent_stream, name='ai_agent_stream'),
]
