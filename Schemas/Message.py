from mongoengine import *
from datetime import *

class Message(Document):
    recipient = ReferenceField("User")
    body = StringField()
    sender = ReferenceField("User")
    timestamp = DateTimeField()

