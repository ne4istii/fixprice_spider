from copy import deepcopy
from datetime import datetime as dt
import json
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import scrapy

import fixprice_scraper.settings as s
from fixprice_scraper.items import Assets, PriceData, Product, Stock


CATEGORY_URLS = []
with open('start_urls.txt') as f:
    for line in f:
        url = line.strip('\n')
        CATEGORY_URLS.append(url)


class CatalogSpider(scrapy.Spider):
    name = 'catalog'
    start_urls = [CATEGORY_URLS.pop()]

    def parse(self, response):
        data = response.body.decode()
        if data:
            self.page = 1
            params = {
                'page': self.page,
                'limit': 24,
                'sort': 'sold'
            }
            url_parsed = urlparse(response.url)
            _ , url_path = url_parsed.path.split('catalog/')
            method = f'{s.POST_CATEGORY_METHOD}/{url_path}?{urlencode(params)}'
            url = urljoin(s.API_BASE_URL, method)
            yield scrapy.Request(
                url=url, method='POST', callback=self.parse_category,
                dont_filter=True)

    def parse_category(self, response):
        """
        Go through all categories from the pre-populated 
        list (from the file start_urls.txt).
        """
        category_data = json.loads(response.body.decode())
        if not category_data:
            try:
                url = CATEGORY_URLS.pop()
                yield scrapy.Request(
                    url=url, method='GET', callback=self.parse,
                    dont_filter=True)
            except IndexError as e:
                self.logger.info('Category urls is over! Finished!')
        else:
            products = [
                product
                for product in category_data
            ]
            for product in products:
                relative_url = product['url']
                method = f'{s.GET_PRODUCT_METHOD}/{relative_url}'
                url = urljoin(s.API_BASE_URL, method)
                yield scrapy.Request(
                    url=url, method='GET', callback=self.parse_product,
                    cb_kwargs={'product_info': product}, dont_filter=True)

            # follow next category page
            self.page += 1
            response_url = deepcopy(response.url)
            parsed_url = urlparse(response_url)
            params = parse_qs(parsed_url.query)
            params['page'] = self.page
            params = urlencode(params, doseq=True)
            url = response_url.replace(parsed_url.query, params)
            yield scrapy.Request(
                url=url, method='POST', callback=self.parse_category,
                dont_filter=True)

    def parse_product(self, response, product_info):
        product = json.loads(response.body.decode())
        item = self.get_product_item(product, product_info)

        # get product in stock
        params = {
            'canPickup': 'all',
            'addressPart': '',
            'inStock': 'true'
        }
        method = f'{s.GET_STORE_BALANCE}/{product['id']}?{urlencode(params)}'
        url = urljoin(s.API_BASE_URL, method)
        yield scrapy.Request(
            url=url, method='GET', callback=self.parse_product_in_stock,
            cb_kwargs={'item': item}, dont_filter=True)

    def parse_product_in_stock(self, response, item):
        """
        Input - api response with a list of dictionaries with data 
        on all stores, including the balance of goods in stock at each store.
        Output is a refilled Item object.
        """
        stock_data = json.loads(response.body.decode())
        count = 0
        for shop_data in stock_data:
            shop_count = shop_data.get('count', 0)
            if isinstance(shop_count, int):
                count += shop_count
        stock = Stock()
        stock['count'] = count
        stock['in_stock'] = True if count > 0 else False
        item['stock'] = stock
        yield item

    def get_product_item(self, product, product_info):
        """
        On input - the raw product data from product api response
        and category api response.
        Output -  fill in Item object.
        """
        item = Product()
        item['timestamp'] = dt.now().timestamp()
        item['RPC'] = product.get('sku', '')
        item['url'] = urljoin(s.BASE_URL, f'catalog/{product.get("url")}')
        item['title'] = product.get('title', '')

        # brand
        brand = product.get('brand', {})
        if brand not in [None, 'None', 'null']:
            item['brand'] = brand.get('title')

        # section
        item['section'] = []
        category_info = product_info.get('category', {})
        if category_info:
            parent_category_info = category_info.get('parentCategory', {})
            if parent_category_info not in ['null', 'None', None, {}, []]:
                parent_category = parent_category_info.get('title', '')
                item['section'].append(parent_category)
            category = category_info.get('title', '')
            item['section'].append(category)

        # marketing_tags
        item['marketing_tags'] = []
        if product.get('isNew'):
            item['marketing_tags'].append('Новинка')
        elif product.get('isPromo'):
            item['marketing_tags'].append('Акция')
        elif product.get('isHit'):
            item['marketing_tags'].append('Хит')

        # price_data
        price_data = PriceData()
        price_data['original'] = 0.0
        try:
            original_price = float(product.get('variants', [])[0]['price'])
            price_data['original'] = original_price
        except Exception as e:
            self.logger.info(f'Product without price: {item["url"]}')
        special_price = product.get('specialPrice', {})
        if (special_price not in [None, 'None', 'null'] and 
                price_data['original']):
            price_data['current'] = float(special_price.get('price'))
            formula = (100 - price_data['current'] * 100 / 
                       price_data['original'])
            discount_percentage = str(round(formula, 1))
            price_data['sale_tag'] = f'Скидка {discount_percentage}%'
        else:
            price_data['current'] = original_price

        item['price_data'] = price_data

        # assets
        assets = Assets()
        image_number = product.get('image')
        images = product.get('images')
        assets['main_image'] = ''
        assets['set_images'] = []
        for image in images:
            assets['set_images'].append(image['src'])
            if not assets['main_image'] and image['id'] == image_number:
                assets['main_image'] = image['src']
        if product.get('videoLink') not in [None, 'None', 'null']:
            assets['video'] = [product.get('videoLink', '')]
        item['assets'] = assets

        # metadata
        metadata = {}
        variants = product.get('variants', [])
        metadata['__description'] = product.get('description', '')
        if variants:
            metadata['product_code'] = variants[0].get('barcode', '')
            metadata['width'] = str(variants[0].get('width', ''))
            metadata['height'] = str(variants[0].get('height', ''))
            metadata['length'] = str(variants[0].get('length', ''))
            metadata['weight'] = str(variants[0].get('weight', ''))
        properties = product.get('properties', [])
        if properties:
            for p in properties:
                if p['alias']:
                    metadata[p['alias']] = p.get('value', '')
        extra_descriptions = product.get('extraDescriptions', [])
        if extra_descriptions:
            for d in extra_descriptions:
                if d['alias']:
                    metadata[d['alias']] = d.get('value', '')
        item['metadata'] = metadata

        # variants
        item['variants'] = product_info.get('variantCount') or 1
        return item
