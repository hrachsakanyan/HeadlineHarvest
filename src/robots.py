"""robots.txt compliance.

Rules follow RFC 9309 (the Robots Exclusion Protocol):

* ``200``            -> obey the rules we were given
* ``404`` / ``410``  -> no rules published, everything is allowed
* ``401`` / ``403``  -> access to the rules is restricted, treat as disallow-all
* ``5xx`` / network  -> unknown state, stay off the site (fail closed)

The parser is ``urllib.robotparser`` from the standard library, but the fetch is
done with ``requests`` so the status codes above can be handled explicitly and
the same User-Agent is used for robots.txt as for the pages themselves.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)


class RobotsPolicy:
    """Fetches and caches one robots.txt per host."""

    def __init__(self, session: requests.Session, user_agent: str, timeout: float = 10.0):
        self.session = session
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}

    def _parser_for(self, url: str) -> RobotFileParser | None:
        """Return a parser for the URL's host, or ``None`` to mean disallow-all."""
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin in self._cache:
            return self._cache[origin]

        robots_url = urljoin(origin, "/robots.txt")
        parser: RobotFileParser | None = RobotFileParser()
        parser.set_url(robots_url)

        try:
            response = self.session.get(robots_url, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.warning("Could not reach %s (%s) - treating the site as off limits", robots_url, exc)
            parser = None
        else:
            status = response.status_code
            if status == 200:
                parser.parse(response.text.splitlines())
                logger.debug("Loaded %s", robots_url)
            elif status in (404, 410):
                parser.parse([])  # empty ruleset == allow everything
                logger.debug("%s returned %s - no restrictions published", robots_url, status)
            elif status in (401, 403):
                logger.warning("%s returned %s - treating the site as off limits", robots_url, status)
                parser = None
            else:
                logger.warning(
                    "%s returned %s - unknown state, treating the site as off limits",
                    robots_url,
                    status,
                )
                parser = None

        self._cache[origin] = parser
        return parser

    def can_fetch(self, url: str) -> bool:
        """Is this URL allowed for our User-Agent?"""
        parser = self._parser_for(url)
        if parser is None:
            return False
        return parser.can_fetch(self.user_agent, url)

    def crawl_delay(self, url: str) -> float | None:
        """Crawl-delay in seconds if the site asks for one, else ``None``."""
        parser = self._parser_for(url)
        if parser is None:
            return None
        try:
            delay = parser.crawl_delay(self.user_agent)
        except AttributeError:  # pragma: no cover - very old Pythons
            return None
        return float(delay) if delay is not None else None
