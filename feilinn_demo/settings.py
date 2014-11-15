# -*- coding: UTF-8 -*-
'''
  Copyright (c) 2014 Present Inc.
'''

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '3!6r-(gkf+0r2loh2tr%-rm18g9i2n1$$27f9rbk0%&k=s+g-t'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []

DBNAME = 'feilinn_demo'

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    #'mongoengine.django.mongo_auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
)

#AUTH_USER_MODEL = 'mongo_auth.MongoUser'
#MONGOENGINE_USER_DOCUMENT = 'mongoengine.django.auth.User'

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

# SESSION_ENGINE = 'mongoengine.django.sessions'
# SESSION_SERIALIZER = 'mongoengine.django.sessions.BSONSerializer'

ROOT_URLCONF = 'feilinn_demo.urls'

WSGI_APPLICATION = 'feilinn_demo.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': {
      'ENGINE': 'django.db.backends.sqlite3',
      'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

AUTHENTICATION_BACKENDS = {
    'mongoengine.django.auth.MongoEngineBackend',
}

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/

STATIC_URL  = '/static/'
STATIC_ROOT = '/var/www/feilinn.com/static'

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'feilinn_demo/templates'),
)

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'feilinn_demo/static/css'),
    os.path.join(BASE_DIR, 'feilinn_demo/static/img'),
    os.path.join(BASE_DIR, 'feilinn_demo/static/img/pic-80'),
    os.path.join(BASE_DIR, 'feilinn_demo/static/img/pic-110'),
    os.path.join(BASE_DIR, 'feilinn_demo/static/img/pic-name-80'),
    os.path.join(BASE_DIR, 'feilinn_demo/static/img/pic-name-110'),
    os.path.join(BASE_DIR, 'feilinn_demo/static/fonts'),
    os.path.join(BASE_DIR, 'feilinn_demo/static/js'),
)
