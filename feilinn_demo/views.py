# -*- coding: UTF-8 -*-
'''
  Copyright (c) 2014 Present Inc.
'''

from django.template.loader import get_template
from django.template import Context, Template, RequestContext
from django.http import HttpResponse
from django.shortcuts import render, render_to_response
from feilinn_demo.models import User, Domain
import datetime

def domain(request):
    dom_list = {'1', '2', '3', '4', '5', '6', '7', '8'}
    tri_list = {'q 1', 'q 2', 'q 3'}
    ship_list = {'title': '领域', 'domain_list' : dom_list, 'question_list': tri_list, 'people_list': tri_list}
    return render_to_response('domain.html', ship_list, context_instance=RequestContext(request))

def topic(request):
    ship_list = {'title': '话题'}
    return render_to_response('topic.html', ship_list,context_instance=RequestContext(request))

'''
TODO:

def index(request):
    return render_to_response('index.html', context_instance=RequestContext(request))

def register(request):
    return render_to_response('register.html', context_instance=RequestContext(request))

def timeline(request):
    return render_to_response('timeline.html', {'user': 'do'}, context_instance=RequestContext(request))
'''
