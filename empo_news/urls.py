from django.urls import path, include

from . import views

app_name = 'empo_news'
urlpatterns = [
    path('submit/', views.submit, name='submit'),
    path('', views.main_page, name='main_page'),
    path('newest', views.new_page, name='new_page'),
    path('notimplemented', views.not_implemented, name='not_implemented'),
    path('login', views.login, name='index'),
    path('accounts/', include('allauth.urls')),
]
