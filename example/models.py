from django.db import models

from pennyblack.models import Newsletter, NewsletterReceiverMixin, NewsletterJobUnitMixin
from pennyblack.content.richtext import TextOnlyNewsletterContent

Newsletter.register_templates({
    'key': 'base',
    'title': 'Generic Newsletter',
    'path': 'base_newsletter.html',
    'regions': (
        ('main', 'Main Region'),
        ),
    })
    
Newsletter.create_content_type(TextOnlyNewsletterContent)

class Group(models.Model, NewsletterJobUnitMixin):
    name = models.CharField(max_length=20)
    class Meta:
        abstract = False
    
    def get_newsletter_receivers(self):
        return self.client_set.all()
    
    def __unicode__(self):
        return self.name
    

class Client(models.Model, NewsletterReceiverMixin):
    fullname = models.CharField(max_length=20)
    email = models.CharField(max_length=100)
    groups = models.ManyToManyField(Group)