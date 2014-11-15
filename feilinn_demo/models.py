# -*- coding: UTF-8 -*-
'''
  Copyright (c) 2014 Present Inc.
'''

from mongoengine import *
from feilinn_demo.settings import DBNAME

connect(DBNAME)

class User(Document):
    email       = StringField(max_length=120, required=True)
    username    = StringField(max_length=120, required=True)
    password    = StringField(max_length=120, required=True)

class Domain(Document):
    name = StringField(max_length=120, required=True)
