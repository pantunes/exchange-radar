from exchange_radar.web.src.settings.base import DEBUG

if DEBUG:
    from starlette.routing import Route

    from exchange_radar.web.src.api.schema import get_openapi_schema
    from exchange_radar.web.src.urls.api import routes

    routes[-1].routes.append(Route("/schema.yaml", endpoint=get_openapi_schema, include_in_schema=False))
