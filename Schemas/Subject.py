from mongoengine import *

class Subject(Document):
    subject = StringField()