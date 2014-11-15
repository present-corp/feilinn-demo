# -*- coding: UTF-8 -*-
'''
  Copyright (c) 2014 Present Inc.
'''

from django.conf.urls import patterns, include, url
from django.contrib import admin

urlpatterns = patterns('',
    url(r'^$',          'feilinn_demo.views.domain'),
    url(r'^domain/$',   'feilinn_demo.views.domain'),
    url(r'^topic/$',    'feilinn_demo.views.topic'),
)
