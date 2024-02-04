from exchange_radar.web.src.settings.base import DEBUG

routes: list = []


if DEBUG:
    from starlette.routing import Route

    from exchange_radar.web.src.api.schema import get_openapi_schema

    routes += [Route("/api/schema.yaml", endpoint=get_openapi_schema, include_in_schema=False)]
