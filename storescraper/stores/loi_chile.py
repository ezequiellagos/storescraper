import logging
from decimal import Decimal

from bs4 import BeautifulSoup

from storescraper.categories import MONITOR, HEADPHONES, STEREO_SYSTEM, \
    MOUSE, NOTEBOOK, TABLET
from storescraper.product import Product
from storescraper.store import Store
from storescraper.utils import session_with_proxy, remove_words


class LoiChile(Store):
    @classmethod
    def categories(cls):
        return [
            MONITOR,
            HEADPHONES,
            STEREO_SYSTEM,
            MOUSE,
            NOTEBOOK,
            TABLET
        ]

    @classmethod
    def discover_urls_for_category(cls, category, extra_args=None):
        url_extensions = [
            ['monitores-tv-y-soportes', MONITOR],
            ['audifonos', HEADPHONES],
            ['parlantes-y-microfonos', STEREO_SYSTEM],
            ['teclados-mouses', MOUSE],
            ['notebooks-y-cumputadoras', NOTEBOOK],
            ['tablets-accesorios', TABLET]
        ]
        session = session_with_proxy(extra_args)
        products_urls = []
        for url_extension, local_category in url_extensions:
            if local_category != category:
                continue
            url_webpage = 'https://loichile.cl/ver/cuadros/{}'.format(
                url_extension)
            data = session.get(url_webpage).text
            soup = BeautifulSoup(data, 'html.parser')
            product_containers = soup.find('ul', 'navexp-rejilla').findAll(
                'li')
            if not product_containers:
                logging.warning('Empty category: ' + url_extension)
                break
            for container in product_containers:
                product_url = container.find('a')['href']
                products_urls.append('https://loichile.cl/' + product_url)
        return products_urls

    @classmethod
    def products_for_url(cls, url, category=None, extra_args=None):
        print(url)
        session = session_with_proxy(extra_args)
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        if not soup.find('div', 'pv3-pv-loi'):
            return []

        name = soup.find('h1', 'nombre-producto-info').text.replace('\t', '') \
            .replace('\n', '')
        sku = soup.find('span', {'id': 'idProducto'}).text
        price = Decimal(remove_words(soup.find('div', 'pv3-pv-loi').text))
        picture_urls = [
            'https://d660b7b9o0mxk.cloudfront.net/_img_productos/' +
            tag['src'].split('_img_productos/')[1] for tag in
            soup.find('div', 'swiper-wrapper').findAll('img')]
        p = Product(
            name,
            cls.__name__,
            category,
            url,
            url,
            sku,
            -1,
            price,
            price,
            'CLP',
            sku=sku,
            picture_urls=picture_urls
        )
        return [p]
