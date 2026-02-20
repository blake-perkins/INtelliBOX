"""Shared dependencies for web routers — templates, static files, sessions."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

import intellibox.database as _database
from intellibox import __version__
from intellibox.settings_service import SettingsService

template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(template_dir))

# Template globals available in all templates
templates.env.globals["get_program_name"] = lambda: SettingsService.get_setting(
    "program_name", ""
)
templates.env.globals["app_version"] = __version__


# Auto-inject current_user into every template context so routes don't
# need to pass it explicitly.  Works with any auth mode.
_original_template_response = templates.TemplateResponse


def _auth_template_response(name, context, **kwargs):
    request = context.get("request")
    if request and hasattr(request.state, "user"):
        context.setdefault("current_user", request.state.user)
    return _original_template_response(name, context, **kwargs)


templates.TemplateResponse = _auth_template_response


def get_session():
    """Get a database session. Delegates to database.get_session() at call time.

    This indirection allows tests to patch intellibox.database.get_session
    once and have all routers pick up the override automatically.
    """
    return _database.get_session()
