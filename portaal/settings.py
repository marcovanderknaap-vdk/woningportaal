"""Instellingen voor het Zeeuws woningportaal.

Gevoelige of omgevingsafhankelijke waarden komen uit omgevingsvariabelen,
zodat dezelfde code lokaal, in GitHub Actions en later op een server draait.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    # Een lege variabele (bijv. een niet-ingevuld GitHub-secret) telt als 'niet ingesteld'
    value = os.environ.get(name)
    return default if value in (None, "") else value


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return value.lower() in {"1", "true", "yes", "ja", "on"}


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-onveilige-sleutel-vervang-in-productie")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.app.github.dev").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "https://*.app.github.dev").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "aanbod",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "portaal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "aanbod.context_processors.portaal",
            ],
        },
    },
]

WSGI_APPLICATION = "portaal.wsgi.application"

# Database: PostgreSQL via DATABASE_URL (productie/test-server), anders SQLite (GitHub, lokaal).
#   DATABASE_URL=postgres://gebruiker:wachtwoord@localhost:5432/portaal
if env("DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"), conn_max_age=600, conn_health_checks=True)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(env("PORTAAL_DB_PATH", BASE_DIR / "data" / "portaal.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "nl"
TIME_ZONE = "Europe/Amsterdam"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("PORTAAL_MEDIA_ROOT", BASE_DIR / "data" / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Portaal ---------------------------------------------------------------
PORTAAL_NAAM = env("PORTAAL_NAAM", "Weune")
# Publiek adres van de site; gebruikt voor de deelafbeelding (og:image) en canonieke links.
PORTAAL_SITE_URL = env("PORTAAL_SITE_URL", "https://www.weune.nl").rstrip("/")
# Mogen zoekmachines de site indexeren? Standaard uit zolang het een test is.
PORTAAL_INDEXEREN = env_bool("PORTAAL_INDEXEREN", False)
# Aantal dagen dat een woning het label 'nieuw' krijgt.
NIEUW_DAGEN = int(env("NIEUW_DAGEN", "14"))
# Hoe lang verkochte woningen nog zichtbaar blijven op de site.
VERKOCHT_ZICHTBAAR_DAGEN = int(env("VERKOCHT_ZICHTBAAR_DAGEN", "30"))
# Hoe lang verkochte woningen nog gecontroleerd worden (daarna niet meer opgehaald).
VERKOCHT_CONTROLE_DAGEN = int(env("VERKOCHT_CONTROLE_DAGEN", "30"))
# User-Agent waarmee de makelaarssites bezocht worden.
SCRAPER_USER_AGENT = env(
    "SCRAPER_USER_AGENT",
    "ZeeuwsWoningportaal/0.1 (aanbodcontrole 1x per dag; deelnemende makelaars)",
)
# Minimale wachttijd tussen verzoeken naar dezelfde site (seconden).
# Een hogere 'Crawl-delay' uit robots.txt gaat altijd voor.
SCRAPER_MIN_DELAY = float(env("SCRAPER_MIN_DELAY", "2"))
SCRAPER_TIMEOUT = float(env("SCRAPER_TIMEOUT", "30"))
# Maximale breedte van de opgeslagen hoofdfoto.
FOTO_MAX_BREEDTE = int(env("FOTO_MAX_BREEDTE", "1200"))

# --- E-mail bij storingen --------------------------------------------------
# Zonder EMAIL_HOST worden e-mails naar de console geschreven.
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("EMAIL_FROM", EMAIL_HOST_USER or "portaal@localhost")
# Komma-gescheiden lijst met ontvangers van het storingsrapport.
RAPPORT_EMAIL = [a.strip() for a in env("RAPPORT_EMAIL", "").split(",") if a.strip()]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"aanbod": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")}},
}
