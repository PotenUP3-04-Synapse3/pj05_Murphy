from backend.app.main import app
from starlette.routing import Route


def test_app_bootstrap_exposes_health_route() -> None:
    route_paths = {route.path for route in app.routes if isinstance(route, Route)}

    assert app.title == "Murphy Developer C Backend"
    assert "/health" in route_paths
