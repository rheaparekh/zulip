# -*- coding: utf-8 -*-
from django.db import models, migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def remove_special_chars_from_streamname(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Stream = apps.get_model('zerver', 'Stream')
    NAME_INVALID_CHARS = ['*', '@', '`', '#']
    for entry in Stream.objects.all():
        stream_name = entry.name

        if (set(stream_name).intersection(NAME_INVALID_CHARS)):
            for char in NAME_INVALID_CHARS:
                stream_name = stream_name.replace(char, ' ')

        entry.name = entry.name.replace(entry.name, stream_name, 1)
        entry.save()

def remove_special_chars_from_username(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    UserProfile = apps.get_model('zerver', 'UserProfile')
    NAME_INVALID_CHARS = ['*', '`', '>', '"', '@', '#']
    for entry in UserProfile.objects.all():
        fullname = entry.full_name
        shortname = entry.short_name

        if (set(fullname).intersection(NAME_INVALID_CHARS)):
            for char in NAME_INVALID_CHARS:
                fullname = fullname.replace(char, ' ')

        if (set(shortname).intersection(NAME_INVALID_CHARS)):
            for char in NAME_INVALID_CHARS:
                shortname = shortname.replace(char, ' ')

        entry.full_name = entry.full_name.replace(entry.full_name, fullname, 1)
        entry.short_name = entry.short_name.replace(entry.short_name, shortname, 1)
        entry.save()

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0121_realm_signup_notifications_stream'),
    ]

    operations = [
        migrations.RunPython(remove_special_chars_from_streamname),
        migrations.RunPython(remove_special_chars_from_username),
    ]
