# coding=utf-8
import exceptions

from django.db import models
from django.db.models import signals
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from feincms.management.checker import check_database_schema
from feincms.models import Base
from feincms.utils import copy_model_instance

from pennyblack import settings

#-----------------------------------------------------------------------------
# Newsletter
#-----------------------------------------------------------------------------
class NewsletterManager(models.Manager):
    def active(self):
        """
        Filters all active newsletters
        """
        return self.filter(active=True)
    
    def massmail(self):
        """
        Filters all newsletter avaiable for massmailing
        """
        return self.active().filter(newsletter_type__in=settings.NEWSLETTER_TYPE_MASSMAIL)
        
    def workflow(self):
        """
        Filters all newsletter avaiable in a workflow eg. signupmail
        """
        return self.active().filter(newsletter_type__in=settings.NEWSLETTER_TYPE_WORKFLOW)
    
    def get_workflow_newsletter_by_name(self, name):
        try:
            return self.workflow().get(name__iexact=name, language=translation.get_language())
        except models.ObjectDoesNotExist:
            pass
        try:
            return self.workflow().get(name__iexact=name, language=settings.LANGUAGE_CODE)
        except models.ObjectDoesNotExist:
            pass
        try:
            return self.workflow().filter(name__iexact=name)[0]
        except:
            return None

class Newsletter(Base):
    """A newsletter with subject and content
    can contain multiple jobs with mails to send"""
    name = models.CharField(verbose_name="Name", help_text="Wird nur intern verwendet.", max_length=100)
    active = models.BooleanField(default=True)
    newsletter_type = models.IntegerField(choices=settings.NEWSLETTER_TYPE,
        verbose_name="Art", help_text="Kann später nicht mehr geändert werden")
    sender = models.ForeignKey('pennyblack.Sender', verbose_name="Absender")
    subject = models.CharField(verbose_name="Betreff", max_length=250)
    reply_email = models.EmailField(verbose_name="Reply-to" ,blank=True)
    language = models.CharField(max_length=6, verbose_name="Sprache", choices=settings.LANGUAGES)
    header_image = models.ForeignKey('medialibrary.MediaFile', verbose_name="Header Image")
    header_url = models.URLField()
    header_url_replaced = models.CharField(max_length=250, default='')
    site = models.ForeignKey('sites.Site', verbose_name="Seite")    
    #ga tracking
    utm_source = models.SlugField(verbose_name="Utm Source", default="newsletter")
    utm_medium = models.SlugField(verbose_name="Utm Medium", default="cpc")
    
    objects = NewsletterManager()

    class Meta:
        ordering = ('subject',)
        verbose_name = "Newsletter"
        verbose_name_plural = "Newsletters"
        app_label = 'pennyblack'
            
    def __unicode__(self):
        return self.name
    
    def is_valid(self):
        if self.subject == '':
            return False
        # todo: check if email is valid
        return True
    
    def create_snapshot(self):
        snapshot = copy_model_instance(self, exclude=('id',))
        snapshot.active = False
        snapshot.save()
        snapshot.copy_content_from(self)
        return snapshot
        
    def get_base_url(self):
        return "http://" + self.site.domain
        
    def replace_links(self, job):
        """
        Searches al links in content sections
        """
        if self.is_workflow():
            job = self.get_default_job()
        for cls in self._feincms_content_types:
            for content in cls.objects.filter(parent=self):
                content.replace_links(job)
                content.save()
        # todo: hier coden
        if self.header_url_replaced != '':
            # try to find the link and compare it to the header_url but
            # replace the link if something goes wrong
            try:
                link_hash = resolve(self.header_url_replaced[len('{{base_url}}'):])[2]['link_hash']
                link = Link.objects.get(link_hash=link_hash)
                if link.link_target == self.header_url:
                    return
            except:
                pass
        self.header_url_replaced = job.add_link(self.header_url)
        self.save()
        
    def get_default_job(self):
        try:
            return self.jobs.get(content_type=None)
        except models.ObjectDoesNotExist:
            return Job.objects.create(newsletter=self, status=32)            
    
    def is_workflow(self):
        return self.newsletter_type in settings.NEWSLETTER_TYPE_WORKFLOW 
    def send(self, person, group=None):
        """
        Sends this newsletter to "person" with optional "group".
        This works only with newsletters which are workflow newsletters.
        """
        if not self.is_workflow():
            raise exceptions.AttributeError('only newsletters with type workflow can be sent')
        # search newsletter job wich hash the same group or create it if it doesn't exist
        try:
            if group:
                ctype = ContentType.objects.get_for_model(group)
                job = self.jobs.get(content_type__pk=ctype.id, object_id=group.id)
            else:
                job = self.jobs.get(content_type=None)
        except models.ObjectDoesNotExist:
            if group:
                kw = {'group_object':group}
            else:
                kw = {}
            job=Job.objects.create(newsletter=self, status=32, **kw) # 32=readonly
        self.replace_links(job)
        mail = job.create_mail(person)
        try:
            message = mail.get_message()
            message.send()
        except:
            raise
        else:
            mail.mark_sent()
            

    
signals.post_syncdb.connect(check_database_schema(Newsletter, __name__), weak=False)
