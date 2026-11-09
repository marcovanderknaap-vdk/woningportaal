"""Beleefd ophalen van pagina's: respecteert robots.txt en een wachttijd per site."""
import logging
import time
from urllib import robotparser
from urllib.parse import urlsplit

import requests
from django.conf import settings

log = logging.getLogger("aanbod.scraper")


class NietToegestaan(Exception):
    """robots.txt van de site staat het ophalen van deze URL niet toe."""


class Fetcher:
    def __init__(self, user_agent=None, min_delay=None, timeout=None):
        self.user_agent = user_agent or settings.SCRAPER_USER_AGENT
        self.min_delay = settings.SCRAPER_MIN_DELAY if min_delay is None else min_delay
        self.timeout = timeout or settings.SCRAPER_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "nl-NL,nl;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._robots = {}
        self._laatste_verzoek = {}
        self.aantal_verzoeken = 0

    # -- robots.txt ---------------------------------------------------------
    def _robots_voor(self, host_url):
        if host_url not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                r = self.session.get(host_url + "/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[host_url] = rp
        return self._robots[host_url]

    def wachttijd(self, url):
        parts = urlsplit(url)
        rp = self._robots_voor(f"{parts.scheme}://{parts.netloc}")
        delay = rp.crawl_delay(self.user_agent) or rp.crawl_delay("*") or 0
        return max(float(delay), self.min_delay)

    # -- ophalen ------------------------------------------------------------
    def get(self, url, check_robots=True, binary=False):
        parts = urlsplit(url)
        host_url = f"{parts.scheme}://{parts.netloc}"
        if check_robots and not self._robots_voor(host_url).can_fetch(self.user_agent, url):
            raise NietToegestaan(url)

        if check_robots:
            wacht = self.wachttijd(url)
            vorige = self._laatste_verzoek.get(parts.netloc)
            if vorige is not None:
                resterend = wacht - (time.monotonic() - vorige)
                if resterend > 0:
                    time.sleep(resterend)

        for poging in range(3):
            try:
                r = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                self.aantal_verzoeken += 1
                self._laatste_verzoek[parts.netloc] = time.monotonic()
                if r.status_code in (429, 502, 503, 504) and poging < 2:
                    time.sleep(10 * (poging + 1))
                    continue
                if not binary and r.encoding is None:
                    r.encoding = r.apparent_encoding
                return r
            except requests.RequestException:
                if poging == 2:
                    raise
                time.sleep(5 * (poging + 1))
        return r
