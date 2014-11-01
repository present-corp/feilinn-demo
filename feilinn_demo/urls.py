from django.conf.urls import patterns, include, url
from django.contrib import admin

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'feilinn_demo.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    # url(r'^admin/', include(admin.site.urls)),
    # url(r'^$',       'feilinn_demo.views.index_page',  name = 'index_page'),
    url(r'^$',       'feilinn_demo.views.index',       name = 'index'),
    url(r'^update/', 'feilinn_demo.views.update',      name = 'update'),
    url(r'^delete/', 'feilinn_demo.views.delete',      name = 'delete'),
    url(r'^clerk/',  'feilinn_demo.views.clerk_page',  name = 'clerk_page'),
)
