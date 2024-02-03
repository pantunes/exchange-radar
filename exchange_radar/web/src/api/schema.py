from starlette.schemas import SchemaGenerator

from exchange_radar import __description__, __title__, __version__

schema = SchemaGenerator(
    {
        "openapi": "3.0.0",
        "info": {"title": __title__, "version": __version__, "description": __description__},
        "servers": [{"url": "http://127.0.0.1:9000/"}],
    }
)


def get_openapi_schema(request):
    return schema.OpenAPIResponse(request=request)
