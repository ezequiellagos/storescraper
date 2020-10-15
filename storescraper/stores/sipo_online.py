import html
import json
import logging
from decimal import Decimal

from bs4 import BeautifulSoup

from storescraper.categories import STEREO_SYSTEM, MEMORY_CARD, \
    USB_FLASH_DRIVE, EXTERNAL_STORAGE_DRIVE, STORAGE_DRIVE, RAM, HEADPHONES, \
    KEYBOARD, MOUSE, KEYBOARD_MOUSE_COMBO, COMPUTER_CASE, MONITOR, WEARABLE
from storescraper.product import Product
from storescraper.store import Store
from storescraper.utils import session_with_proxy, remove_words


class SipoOnline(Store):
    @classmethod
    def categories(cls):
        return [
            STEREO_SYSTEM,
            MEMORY_CARD,
            USB_FLASH_DRIVE,
            EXTERNAL_STORAGE_DRIVE,
            STORAGE_DRIVE,
            RAM,
            HEADPHONES,
            KEYBOARD,
            MOUSE,
            KEYBOARD_MOUSE_COMBO,
            COMPUTER_CASE,
            MONITOR,
            WEARABLE
        ]

    @classmethod
    def discover_urls_for_category(cls, category, extra_args=None):
        url_extensions = [
            ['parlante-musica', STEREO_SYSTEM],
            ['almacenamiento/memorias', MEMORY_CARD],
            ['almacenamiento/pendrives', USB_FLASH_DRIVE],
            ['almacenamiento/disco-duro-externo', EXTERNAL_STORAGE_DRIVE],
            ['almacenamiento/disco-duro-interno', STORAGE_DRIVE],
            ['almacenamiento/memoria-ram', RAM],
            ['computacion/audifono-pc', HEADPHONES],
            # Gamer Headphones
            ['zona-gamer/audifono-gamer', HEADPHONES],
            ['computacion/teclado', KEYBOARD],
            # Gamer Keyboard
            ['zona-gamer/teclado-gamer', KEYBOARD],
            ['computacion/mouse', MOUSE],
            # Gamer Mouse
            ['zona-gamer/mouse-gamer', MOUSE],
            ['computacion/combo-computacion', KEYBOARD_MOUSE_COMBO],
            # Gamer Combo
            ['zona-gamer/kit-gamer', KEYBOARD_MOUSE_COMBO],
            ['componentes-pc/gabinetes', COMPUTER_CASE],
            ['componentes-pc/monitores', MONITOR],
            ['smartwatch', WEARABLE]
        ]

        session = session_with_proxy(extra_args)
        product_urls = []
        for url_extension, local_category in url_extensions:
            if local_category != category:
                continue
            page = 1
            while True:
                if page > 10:
                    raise Exception('page overflow: ' + url_extension)
                url_webpage = 'https://sipoonline.cl/product-category/' \
                              '{}/page/{}/'.format(url_extension, page)
                data = session.get(url_webpage).text
                soup = BeautifulSoup(data, 'html.parser')
                product_containers = soup.findAll('div', 'nv-product-content')
                if not product_containers:
                    if page == 1:
                        logging.warning('Empty category: ' + url_extension)
                    break
                for container in product_containers:
                    product_url = container.find('a')['href']
                    product_urls.append(product_url)
                page += 1
        return product_urls

    @classmethod
    def products_for_url(cls, url, category=None, extra_args=None):
        session = session_with_proxy(extra_args)
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        name = soup.find('h1', 'product_title').text
        variants = soup.find('form', 'variations_form')
        if not variants:
            variants = soup.find('div', 'variations_form')

        if variants:
            products = []
            container_products = json.loads(
                html.unescape(variants['data-product_variations']))
            for product in container_products:
                if len(product['attributes']) > 0:
                    variant_name = name + " - " + next(
                        iter(product['attributes'].values()))
                else:
                    variant_name = name
                sku = str(product['variation_id'])
                if product['availability_html'] != '':
                    stock = int(
                        BeautifulSoup(product['availability_html'],
                                      'html.parser').text.split()[0])
                else:
                    stock = -1
                price = Decimal(product['display_price'])
                picture_urls = [product['image']['src']]
                p = Product(
                    variant_name,
                    cls.__name__,
                    category,
                    url,
                    url,
                    sku,
                    stock,
                    price,
                    price,
                    'CLP',
                    sku=sku,
                    picture_urls=picture_urls

                )
                products.append(p)
            return products
        else:
            stock_container = soup.find('p', 'stock in-stock')
            if stock_container:
                stock = int(stock_container.text.split()[0])
            else:
                stock = -1
            sku = soup.find('button', 'single_add_to_cart_button')['value']
            price_container = soup.find('p', 'price')
            if price_container.find('ins'):
                price = Decimal(
                    remove_words(price_container.find('ins').find('bdi').text))
            else:
                price = Decimal(remove_words(price_container.find('bdi').text))
            picture_containers = soup.find('div',
                                           'woocommerce-product-gallery') \
                .findAll('img')
            picture_urls = [tag['src'] for tag in picture_containers]
            p = Product(
                name,
                cls.__name__,
                category,
                url,
                url,
                sku,
                stock,
                price,
                price,
                'CLP',
                sku=sku,
                picture_urls=picture_urls
            )
            return [p]
