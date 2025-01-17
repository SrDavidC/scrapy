import logging
from typing import Any

from twisted.python.failure import Failure

from scrapy import Request
from scrapy.exceptions import _InvalidOutput
from scrapy.http import Response
from scrapy.spidermiddlewares.handler.basespidermiddleware import BaseSpiderMiddleware

logger = logging.getLogger(__name__)


class DepthMiddleware(BaseSpiderMiddleware):
    _sm_component_name = "DepthMiddleware"

    def __init__(self, maxdepth, stats, verbose_stats=False, prio=1):
        self.maxdepth = maxdepth
        self.stats = stats
        self.verbose_stats = verbose_stats
        self.prio = prio

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        maxdepth = settings.getint("DEPTH_LIMIT")
        verbose = settings.getbool("DEPTH_STATS_VERBOSE")
        prio = settings.getint("DEPTH_PRIORITY")
        return cls(maxdepth, crawler.stats, verbose, prio)

    def handle(self, packet: Any, spider, result):
        try:
            if isinstance(packet, Response):
                self.process_spider_output(packet, result, spider)
                self.check_integrity(result)
        except _InvalidOutput:
            raise
        except Exception:
            return self.scrape_func(Failure(), packet, spider)

        if self._next_handler:
            return self._next_handler.handle(packet, spider, result)

        return

    def process_spider_output(self, response, result, spider):
        self._init_depth(response, spider)
        return (r for r in result or () if self._filter(r, response, spider))

    def process_spider_input(self, request, spider, result):
        return result

    def _init_depth(self, response, spider):
        # base case (depth=0)
        if "depth" not in response.meta:
            response.meta["depth"] = 0
            if self.verbose_stats:
                self.stats.inc_value("request_depth_count/0", spider=spider)

    def _filter(self, request, response, spider):
        if not isinstance(request, Request):
            return True
        depth = response.meta["depth"] + 1
        request.meta["depth"] = depth
        if self.prio:
            request.priority -= depth * self.prio
        if self.maxdepth and depth > self.maxdepth:
            logger.debug(
                "Ignoring link (depth > %(maxdepth)d): %(requrl)s ",
                {"maxdepth": self.maxdepth, "requrl": request.url},
                extra={"spider": spider},
            )
            return False
        if self.verbose_stats:
            self.stats.inc_value(f"request_depth_count/{depth}", spider=spider)
        self.stats.max_value("request_depth_max", depth, spider=spider)
        return True
