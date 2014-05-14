from django.conf.urls import patterns, url

urlpatterns = patterns('zencoder.views',
    url(r'^new$', "video", name="video-new"),  # noqa
    url(r'^(?P<video_id>\d+)', "video", name="video-detail"),
    url(r'^encode$', 'encode'),
    url(r'^notify$', 'notify')
)