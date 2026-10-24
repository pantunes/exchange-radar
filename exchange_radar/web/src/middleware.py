import secrets

from starlette.middleware.base import BaseHTTPMiddleware

# Sources the pages legitimately need (see templates/snippets/headers.j2):
#   - jQuery from code.jquery.com and web-socket-js from cdnjs.cloudflare.com
#   - Google Fonts CSS from fonts.googleapis.com, font files from fonts.gstatic.com
#   - our own static JS/CSS and same-origin WebSocket + XHR calls ('self')
# Inline <script> blocks carry a per-response nonce; because 'unsafe-inline' is
# absent from script-src, injected inline scripts/handlers (e.g. a stray
# <img onerror=...> reaching the trade-feed innerHTML sink) are refused by the
# browser. Inline style="" attributes are allowed via style-src 'unsafe-inline'.
CSP_TEMPLATE = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}' https://code.jquery.com https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set a nonce-based CSP and baseline security headers on every HTTP response.

    The headers are also typically set at the reverse proxy; setting them here
    guarantees they are present even on error responses and even if the proxy
    config drifts.
    """

    async def dispatch(self, request, call_next):
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        response.headers["Content-Security-Policy"] = CSP_TEMPLATE.format(nonce=nonce)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "no-referrer, strict-origin-when-cross-origin")
        return response
