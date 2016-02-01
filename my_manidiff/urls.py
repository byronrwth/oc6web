from django.conf.urls import patterns, include, url
from apps.my_manidiff import views


urlpatterns = patterns('',
            url(r'^$', views.index, name='index'),
            url(r'^ajax$', views.ajax, name='ajax'),
        )