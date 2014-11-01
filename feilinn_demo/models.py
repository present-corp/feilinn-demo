from mongoengine import *
from feilinn_demo.settings import DBNAME

connect(DBNAME)

class Post(Document):
    title       = StringField(max_length=120, required=True)
    content     = StringField(max_length=500, required=True)
    last_update = DateTimeField(required=True)
