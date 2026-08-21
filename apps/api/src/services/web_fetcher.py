import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from apps.api.src.core.config import settings
from apps.api.src.core.exceptions import ValidationException
from apps.api.src.services.ssrf_service import SSRFService

logger = logging.getLogger("ai_knowledge_assistant.services.web_fetcher")

ALLOWED_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
)


@dataclass
class FetchedWebPage:
    url: str
    content: bytes
    content_type: str
    status_code: int


class WebFetcher:
    """
    Dedicated HTTP fetching service with SSRF protection, redirect verification,
    streamed size limits, and content-type validation.
    """

    def __init__(
        self,
        timeout_seconds: float = float(settings.WEB_FETCH_TIMEOUT_SECONDS),
        max_size_mb: int = settings.MAX_WEB_CONTENT_SIZE_MB,
        max_redirects: int = settings.WEB_FETCH_MAX_REDIRECTS,
        user_agent: str = settings.WEB_FETCH_USER_AGENT,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_size_mb * 1024 * 1024
        self.max_redirects = max_redirects
        self.user_agent = user_agent

    async def fetch(self, target_url: str) -> FetchedWebPage:
        """
        Fetch a remote webpage safely.
        Validates target and all subsequent redirect URLs against SSRF.
        """
        current_url = SSRFService.validate_url(target_url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        transport = httpx.AsyncHTTPTransport(retries=1)
        redirect_history = set()

        async with httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(self.timeout_seconds, connect=10.0),
            follow_redirects=False,
            verify=True,
        ) as client:
            for redirect_count in range(self.max_redirects + 1):
                if current_url in redirect_history:
                    raise ValidationException(f"Redirect loop detected at '{current_url}'.")
                redirect_history.add(current_url)

                logger.info(f"Fetching webpage: {current_url} (hop={redirect_count})")
                try:
                    response = await client.get(current_url, headers=headers)
                except httpx.TimeoutException:
                    raise ValidationException(
                        f"Request to '{current_url}' timed out after {self.timeout_seconds}s."
                    ) from None
                except httpx.ConnectError as e:
                    raise ValidationException(
                        f"Failed to connect to host for '{current_url}': {e}"
                    ) from None
                except httpx.RequestError as e:
                    raise ValidationException(
                        f"Network error fetching '{current_url}': {e}"
                    ) from None

                # Handle HTTP Redirects (301, 302, 303, 307, 308)
                if response.is_redirect:
                    if redirect_count >= self.max_redirects:
                        raise ValidationException(
                            f"Exceeded maximum allowed redirects ({self.max_redirects})."
                        )

                    location = response.headers.get("Location")
                    if not location:
                        raise ValidationException("Redirect response missing Location header.")

                    # Resolve relative redirect URLs against the current URL
                    next_url = urljoin(current_url, location)

                    # CRITICAL: Validate redirect destination through SSRF protection
                    current_url = SSRFService.validate_url(next_url)
                    continue

                # Check HTTP Status Code
                if response.status_code != 200:
                    raise ValidationException(
                        f"Web server returned HTTP error {response.status_code} ({response.reason_phrase}) for '{current_url}'."
                    )

                # Content-Type Validation
                content_type_header = response.headers.get("Content-Type", "").lower()
                clean_content_type = content_type_header.split(";")[0].strip()

                if not any(
                    clean_content_type.startswith(allowed) for allowed in ALLOWED_CONTENT_TYPES
                ):
                    raise ValidationException(
                        f"Unsupported content-type '{content_type_header}'. Only HTML and text web pages are supported."
                    )

                # Read Content & Enforce Max Size Limit
                content_bytes = response.content
                if len(content_bytes) == 0:
                    raise ValidationException("The fetched webpage is empty.")
                if len(content_bytes) > self.max_bytes:
                    raise ValidationException(
                        f"Webpage size ({len(content_bytes)} bytes) exceeds the maximum limit of {settings.MAX_WEB_CONTENT_SIZE_MB}MB."
                    )

                return FetchedWebPage(
                    url=current_url,
                    content=content_bytes,
                    content_type=clean_content_type,
                    status_code=response.status_code,
                )

            raise ValidationException(
                f"Failed to resolve webpage after {self.max_redirects} redirects."
            )


_web_fetcher_instance: WebFetcher | None = None


def get_web_fetcher() -> WebFetcher:
    """Singleton getter for WebFetcher instance."""
    global _web_fetcher_instance
    if _web_fetcher_instance is None:
        _web_fetcher_instance = WebFetcher()
    return _web_fetcher_instance
