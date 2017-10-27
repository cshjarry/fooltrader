import json
from datetime import datetime

import scrapy
from scrapy import Request
from scrapy import signals

from fooltrader.consts import SSE_KDATA_HEADER
from fooltrader.settings import STOCK_START_CODE, STOCK_END_CODE, TIME_FORMAT_DAY
from fooltrader.utils.utils import get_security_item, get_sh_stock_list_path, \
    get_sz_stock_list_path, \
    get_trading_dates_path_sse


class StockTradingDateSpider(scrapy.Spider):
    name = "stock_trading_date"

    custom_settings = {
        # 'DOWNLOAD_DELAY': 2,
        # 'CONCURRENT_REQUESTS_PER_DOMAIN': 8,

        'SPIDER_MIDDLEWARES': {
            'fooltrader.middlewares.FoolErrorMiddleware': 1000,
        }
    }

    def yield_request(self, item):

        data_path = get_trading_dates_path_sse(item)  # get day k data
        url = self.get_k_data_url(item['exchange'], item['code'])
        yield Request(url=url, headers=SSE_KDATA_HEADER,
                      meta={'path': data_path, 'item': item},
                      callback=self.download_day_k_data)

    def start_requests(self):
        item = self.settings.get("security_item")
        if item:
            for request in self.yield_request(item):
                yield request
        else:
            stock_files = (get_sh_stock_list_path(), get_sz_stock_list_path())
            for stock_file in stock_files:
                for item in get_security_item(stock_file):
                    # 设置抓取的股票范围
                    if STOCK_START_CODE <= item['code'] <= STOCK_END_CODE:
                        for request in self.yield_request(item):
                            yield request

    def download_day_k_data(self, response):
        path = response.meta['path']
        item = response.meta['item']

        trading_dates = []

        try:
            tmp_str = response.text
            json_str = tmp_str[tmp_str.index('{'):tmp_str.index('}') + 1]
            tmp_json = json.loads(json_str)

            # parse the trading dates
            dates = [items[0] for items in tmp_json['kline']]
            trading_dates = [datetime.strptime(str(the_date), '%Y%m%d').strftime(TIME_FORMAT_DAY) for the_date in dates]


        except Exception as e:
            self.logger.error('error when getting k data url={} error={}'.format(response.url, e))

        if len(trading_dates) > 0:
            try:
                with open(get_trading_dates_path_sse(item), "w") as f:
                    json.dump(trading_dates, f)
            except Exception as e:
                self.logger.error(
                    'error when saving trading dates url={} path={} error={}'.format(response.url, path, e))

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(StockTradingDateSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider, reason):
        spider.logger.info('Spider closed: %s,%s\n', spider.name, reason)

    def get_k_data_url(self, exchange, code):
        return 'http://yunhq.sse.com.cn:32041/v1/{}1/dayk/{}?callback=jQuery111202351405749576012_1507560840520&select=date&begin=0&end=10000&_=1507560840536'.format(
            exchange, code)
