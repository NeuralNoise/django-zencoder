import importlib
import json
import requests


from django.core.urlresolvers import reverse
from django.db import models
from json_field import JSONField

from .conf import settings


def sort_video(source):
    try:
        weight = settings.VIDEO_PREFERENCES.index(source.content_type)
    except:
        weight = len(settings.VIDEO_PREFERENCES) + 1
    return weight * (source.width or 1)


class Video(models.Model):
    """This is a very lightweight model that basically wraps an externally available set of sources
    for a given video."""

    name = models.CharField(max_length=255)
    poster = models.URLField(null=True, blank=True)
    input = models.URLField(null=True, blank=True)

    def __unicode__(self):
        return self.name

    def ordered_sources(self):
        return sorted(list(self.sources.all()), key=sort_video)


class Source(models.Model):
    video = models.ForeignKey(Video, related_name="sources")
    url = models.URLField()
    content_type = models.CharField(max_length=100)
    width = models.IntegerField(null=True, blank=True)
    bitrate = models.IntegerField(null=True, blank=True, help_text="In kilobits per second")

    class Meta:
        ordering = ("width", "bitrate")


class JobManager(models.Manager):

    def start(self, video):
        job = self.model(video=video)
        job.start()
        job.save()
        return job


class Job(models.Model):

    NOT_STARTED = 0
    COMPLETE = 1
    IN_PROGRESS = 2
    FAILED = 3
    STATUSES = (
        (NOT_STARTED, 'Not started'),
        (COMPLETE, 'Complete'),
        (IN_PROGRESS, 'In Progress'),
        (FAILED, 'Failed')
    )

    objects = JobManager()
    AUTH_HEADERS = {'Zencoder-Api-Key': settings.ZENCODER_API_KEY}

    video = models.ForeignKey(Video)
    status = models.IntegerField(choices=STATUSES, default=NOT_STARTED, help_text="The encoding status")
    job_id = models.IntegerField()
    data = JSONField()

    def start(self):
        base_url = "s3://{}/{}/{}/".format(
            settings.VIDEO_ENCODING_BUCKET,
            settings.VIDEO_ENCODING_DIRECTORY,
            self.video.pk)
        payload = {
            "input": self.video.input,
            "base_url": base_url,
            "outputs": settings.ZENCODER_OUTPUTS,
            "notifications": [{
                "url": reverse("video.views.notify")
            }]
        }

        response = requests.post(
            "https://app.zencoder.com/api/v2/jobs",
            data=json.dumps(payload),
            headers=self.AUTH_HEADERS)

        if response.status_code != 201:
            raise Exception("Zencoder response <{}>".format(response.status_code))
        
        self.data = response.json()
        self.job_id = self.data.get('id')
        self.status = Job.IN_PROGRESS

    def cancel(self):
        url = "https://app.zencoder.com/api/v2/jobs/{}/cancel.json".format(self.job_id)
        response = requests.put(url, headers=self.AUTH_HEADERS)
        if response.status_code != 204:
            raise Exception("Couldn't cancel the job!")
        self.status = Job.FAILED
