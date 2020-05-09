import os
import os.path
import pathlib

from django.core.files import File
from django.conf import settings
from huey.contrib.djhuey import task

from .models import SeparatedSong, YouTubeFetchTask
from .separate import SpleeterSeparator
from .youtubedl import *

@task()
def separate_task(separate_song):
    separate_song.status = SeparatedSong.Status.IN_PROGRESS
    separate_song.save()
    try:
        # Get paths
        directory = os.path.join(settings.MEDIA_ROOT, settings.SEPARATE_DIR, str(separate_song.id))
        filename = separate_song.formatted_name() + '.mp3'
        rel_media_path = os.path.join(settings.SEPARATE_DIR, str(separate_song.id), filename)
        rel_path = os.path.join(settings.MEDIA_ROOT, rel_media_path)
        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)

        parts = {
            'vocals': separate_song.vocals,
            'drums': separate_song.drums,
            'bass': separate_song.bass,
            'other': separate_song.other
        }
        separator = SpleeterSeparator()
        separator.predict(parts, separate_song.source_path(), rel_path)

        # Check file exists
        if os.path.exists(rel_path):
            separate_song.status = SeparatedSong.Status.DONE
            separate_song.file.name = rel_media_path
            separate_song.save()
        else:
            raise Exception('Error writing to file')
    except BaseException as error:
        separate_song.status = SeparatedSong.Status.ERROR
        separate_song.error = str(error)
        separate_song.save()

@task(retries=2)
def fetch_youtube_audio(source_file, artist, title, link):
    fetch_task = source_file.youtube_fetch_task
    fetch_task.status = YouTubeFetchTask.Status.IN_PROGRESS
    fetch_task.save()

    try:
        # Get paths
        directory = os.path.join(settings.MEDIA_ROOT, settings.UPLOAD_DIR, str(source_file.id))
        filename = artist + ' - ' + title + get_file_ext(link)
        rel_media_path = os.path.join(settings.UPLOAD_DIR, str(fetch_task.id), filename)
        rel_path = os.path.join(settings.MEDIA_ROOT, rel_media_path)
        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
        download_audio(link, rel_path)

        # Check file exists
        if os.path.exists(rel_path):
            fetch_task.status = YouTubeFetchTask.Status.DONE
            source_file.file.name = rel_media_path
            fetch_task.save()
            source_file.save()
        else:
            raise Exception('Error writing to file')
    except BaseException as error:
        fetch_task.status = YouTubeFetchTask.Status.ERROR
        fetch_task.save()