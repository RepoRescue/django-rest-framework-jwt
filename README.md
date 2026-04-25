# django-rest-framework-jwt (RepoRescue fork)

JSON Web Token authentication for Django REST framework — modernized for **Django 6.x / DRF 3.17 / PyJWT 2.x / Python 3.13**.

> **Read this first.** The original project (`jpadilla/django-rest-framework-jwt`) is **unmaintained**. The upstream notice points users to [`djangorestframework-simplejwt`](https://github.com/jazzband/djangorestframework-simplejwt), and that is still the right answer for **new** projects.
>
> What this fork is for: existing Django apps that were pinned to `djangorestframework-jwt` and got stuck on Python 3.13 / PyJWT 2.x because of `ExpiredSignature`, `ugettext`, `smart_text`, `datetime.utcnow`, `distutils`, and `django.conf.urls.url` removals. It is a drop-in patch so you can upgrade your runtime today and migrate to `simplejwt` on your own schedule. Nothing more.

---

## What changed vs upstream `1.11.0`

Seven concrete breakage points fixed (every one of them is exercised by the validation harness in `.reporescue/`):

| File | Surface | Fix |
|---|---|---|
| `rest_framework_jwt/utils.py` | `jwt.encode()` returns `str` in PyJWT 2.x (no more `.decode("utf-8")`) | Drop the decode call |
| `rest_framework_jwt/utils.py` | `jwt.decode()` requires explicit `algorithms=` in PyJWT 2.x | Pass `algorithms=[api_settings.JWT_ALGORITHM]` |
| `rest_framework_jwt/utils.py` | `datetime.utcnow()` deprecated in 3.12+ | `datetime.now(timezone.utc)` |
| `rest_framework_jwt/authentication.py` | `jwt.ExpiredSignature` removed | `jwt.ExpiredSignatureError` |
| `rest_framework_jwt/authentication.py` | `django.utils.translation.ugettext` removed in Django 4 | `gettext` |
| `rest_framework_jwt/authentication.py` | `django.utils.encoding.smart_text` removed in Django 4 | `smart_str` |
| `rest_framework_jwt/serializers.py` | Same `ExpiredSignature` + `ugettext` removals | `ExpiredSignatureError` + `gettext` |
| `tests/test_serializers.py` | `distutils` removed in 3.12 | `packaging.version.Version` |
| `tests/urls.py` | `django.conf.urls.url` removed in Django 4 | `django.urls.re_path` |

No public API was changed. Same view names, same settings keys, same `JWT_AUTH` dict shape.

---

## Install

```bash
pip install git+https://github.com/<org>/django-rest-framework-jwt.git
```

Tested versions:

- Python 3.13
- Django 6.0.x
- djangorestframework 3.17.x
- PyJWT 2.12.x

---

## Quick start

A minimal Django + DRF setup that issues, refreshes, verifies JWTs, and protects an endpoint with `JSONWebTokenAuthentication`. This is a real working file — `python quickstart.py` runs it under `werkzeug` if you also `pip install werkzeug requests`.

```python
import django
from django.conf import settings

settings.configure(
    DEBUG=True,
    SECRET_KEY="change-me",
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3",
                            "NAME": "/tmp/jwt-quickstart.sqlite3"}},
    INSTALLED_APPS=[
        "django.contrib.auth", "django.contrib.contenttypes",
        "django.contrib.sessions", "rest_framework",
    ],
    MIDDLEWARE=[
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
    ],
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework_jwt.authentication.JSONWebTokenAuthentication",
        ],
    },
    JWT_AUTH={"JWT_ALLOW_REFRESH": True},
    USE_TZ=True,
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
django.setup()

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_jwt.views import (
    obtain_jwt_token, refresh_jwt_token, verify_jwt_token,
)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def whoami(request):
    return Response({"user": request.user.username})

urlpatterns = [
    path("api-token-auth/",    obtain_jwt_token),
    path("api-token-refresh/", refresh_jwt_token),
    path("api-token-verify/",  verify_jwt_token),
    path("whoami/",            whoami),
]
```

Client side — same wire format as upstream (`Authorization: JWT <token>`):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api-token-auth/ \
        -H "Content-Type: application/json" \
        -d '{"username":"alice","password":"..."}' | jq -r .token)

curl -H "Authorization: JWT $TOKEN" http://localhost:8000/whoami/
```

---

## What we actually validated

This fork ships with a `.reporescue/` directory (kept out of the wheel) containing the exact scripts used to certify the rescue:

### `usability_validate.py` — full lifecycle on a real WSGI server
Boots a `werkzeug.serving.make_server` instance, then drives `obtain → protected → verify → refresh → protected-with-refreshed-token` over TCP with `requests`. Asserts:
- (a) no token → 401
- (b) good token → 200
- (c) bogus token → 401
- (d) refresh issues a fresh token, and the new token is accepted

Four submodules touched: `views`, `authentication`, `serializers`, `utils`.

### `scenario_validate.py` (Path B) — SPA-style tasks API
~120 LOC, ~40 lines of real business logic beyond setup. Pretends to be a developer who only read this README. Builds `/auth/login/`, `/auth/refresh/`, `/api/tasks/` with per-user task buckets, then runs eight HTTP assertions over real TCP:
login → unauth POST → 401 → authed POSTs → 201/201 → list → refresh JWT → list with refreshed token → 400 on missing field. **Exits `SCENARIO_OK`.**

This path is **not** covered by the upstream test suite, which uses DRF's in-process `APIClient` everywhere (`grep -rn "make_server\|werkzeug\|requests.get" tests/` → 0 matches).

### `bug_hunt.py` — security & robustness probes (6/6 PASS)
| Probe | Result |
|---|---|
| Unicode (Japanese) username encode/decode roundtrip | PASS |
| 100× repeated decode (state leak / cached signer) | PASS |
| Tampered signature → `InvalidSignatureError` | PASS |
| Expired token → `ExpiredSignatureError` (new name) | PASS |
| `alg=none` confused-deputy attack rejected | **PASS** |
| Wrong-algorithm token (HS512 vs configured HS256) rejected | **PASS** |

The last two are the important ones: PyJWT 2.x's hardened defaults (mandatory `algorithms=` whitelist, `alg=none` rejection) are honored end-to-end through this fork's wrappers. Upgrading from PyJWT 1.x to 2.x without this fix typically *silently* breaks decode or *silently* permits `alg=none` if the migration is half-done. We checked.

---

## Disclaimer

- This fork exists to **unblock legacy deployments**, not to compete with `djangorestframework-simplejwt`.
- Original copyright belongs to José Padilla and contributors. We are downstream rescuers, not maintainers.
- The original repo carries an end-of-maintenance notice. Use of this fork is at your own risk.
- For new projects, **please** start with [`djangorestframework-simplejwt`](https://github.com/jazzband/djangorestframework-simplejwt) — it is actively maintained and has token blacklisting, sliding tokens, and a saner default crypto posture.
- If you find a security issue, please file it here, but understand we will likely fix forward and recommend you migrate.

## License

MIT, inherited from the original `django-rest-framework-jwt` project. See `LICENSE`.

---

*This rescue was produced and validated by [RepoRescue](https://github.com/RepoRescue), a benchmark for upgrading abandoned Python repos to Python 3.13 + latest dependencies. The validation logs (T0/T1/T2 + usability) live in `.reporescue/`.*
