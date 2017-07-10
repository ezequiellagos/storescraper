from celery import shared_task, group
from celery.utils.log import get_task_logger

from .product import Product
from .utils import get_store_class_by_name, chunks

logger = get_task_logger(__name__)


class Store:
    preferred_queue = 'us'
    preferred_discover_urls_concurrency = 5
    preferred_products_for_url_concurrency = 40
    prefer_async = True

    ##########################################################################
    # API methods
    ##########################################################################

    @classmethod
    def products(cls, product_types=None, async=None, extra_args=None,
                 queue=None, discover_urls_concurrency=None,
                 products_for_url_concurrency=None):
        if product_types is None:
            product_types = cls.product_types()
        else:
            product_types = [ptype for ptype in cls.product_types()
                             if ptype in product_types]

        if async is None:
            async = cls.prefer_async

        if queue is None:
            queue = cls.preferred_queue

        if discover_urls_concurrency is None:
            discover_urls_concurrency = cls.preferred_discover_urls_concurrency

        if products_for_url_concurrency is None:
            products_for_url_concurrency = \
                cls.preferred_products_for_url_concurrency

        logger.info('Obtaining products from: {}'.format(cls.__name__))

        discovered_urls_with_types = cls.discover_urls_for_product_types(
            product_types=product_types,
            async=async,
            extra_args=extra_args,
            queue=queue,
            discover_urls_concurrency=discover_urls_concurrency
        )

        return cls.products_for_urls(
            discovered_urls_with_types,
            async=async,
            extra_args=extra_args,
            queue=queue,
            products_for_url_concurrency=products_for_url_concurrency)

    @classmethod
    def discover_urls_for_product_types(cls, product_types=None, async=None,
                                        extra_args=None, queue=None,
                                        discover_urls_concurrency=None):
        if product_types is None:
            product_types = cls.product_types()
        else:
            product_types = [ptype for ptype in cls.product_types()
                             if ptype in product_types]

        if async is None:
            async = cls.prefer_async

        if queue is None:
            queue = cls.preferred_queue

        if discover_urls_concurrency is None:
            discover_urls_concurrency = cls.preferred_discover_urls_concurrency

        logger.info('Discovering URLs for: {}'.format(cls.__name__))

        discovered_urls_with_types = []

        if async:
            product_type_chunks = chunks(
                product_types, discover_urls_concurrency)

            for product_type_chunk in product_type_chunks:
                chunk_tasks = []

                logger.info('Discovering URLs for: {}'.format(
                    product_type_chunk))

                for product_type in product_type_chunk:
                    task = cls.discover_urls_for_product_type_task.s(
                        cls.__name__, product_type, extra_args)
                    task.set(queue='storescraper_discover_urls_for_'
                                   'product_type_' + queue)
                    chunk_tasks.append(task)
                tasks_group = cls.create_celery_group(chunk_tasks)

                for idx, task_result in enumerate(tasks_group.get()):
                    product_type = product_type_chunk[idx]
                    logger.info('Discovered URLs for {}:'.format(product_type))
                    for discovered_url in task_result:
                        logger.info(discovered_url)
                        discovered_urls_with_types.append({
                            'url': discovered_url,
                            'product_type': product_type
                        })
        else:
            for product_type in product_types:
                for url in cls.discover_urls_for_product_type(
                        product_type, extra_args):
                    discovered_urls_with_types.append({
                        'url': url,
                        'product_type': product_type
                    })

        return discovered_urls_with_types

    @classmethod
    def products_for_urls(cls, discovery_urls_with_types, async=None,
                          extra_args=None, queue=None,
                          products_for_url_concurrency=None):
        if async is None:
            async = cls.prefer_async

        if queue is None:
            queue = cls.preferred_queue

        if products_for_url_concurrency is None:
            products_for_url_concurrency = \
                cls.preferred_products_for_url_concurrency

        products = []

        if async:
            discovered_urls_with_types_chunks = chunks(
                discovery_urls_with_types, products_for_url_concurrency)

            for discovered_urls_with_types_chunk in \
                    discovered_urls_with_types_chunks:
                chunk_tasks = []

                for discovered_url_entry in discovered_urls_with_types_chunk:
                    task = cls.products_for_url_task.s(
                        cls.__name__, discovered_url_entry['url'],
                        discovered_url_entry['product_type'], extra_args)
                    task.set(queue='storescraper_products_for_url_' + queue)
                    chunk_tasks.append(task)

                tasks_group = cls.create_celery_group(chunk_tasks)

                for task_result in tasks_group.get():
                    for serialized_product in task_result:
                        product = Product.deserialize(serialized_product)
                        products.append(product)
        else:
            for discovered_url_entry in discovery_urls_with_types:
                products.extend(cls.products_for_url(
                    discovered_url_entry['url'],
                    discovered_url_entry['product_type'],
                    extra_args))

        return products

    ##########################################################################
    # Celery tasks wrappers
    ##########################################################################

    @staticmethod
    @shared_task
    def products_task(store_class_name, product_types=None, async=True,
                      extra_args=None, queue=None,
                      discover_urls_concurrency=None,
                      products_for_url_concurrency=None):
        store = get_store_class_by_name(store_class_name)
        return store.products(product_types, async, extra_args, queue,
                              discover_urls_concurrency,
                              products_for_url_concurrency)

    @staticmethod
    @shared_task
    def discover_urls_for_product_types_task(
            store_class_name, product_types=None, async=None, extra_args=None,
            queue=None, discover_urls_concurrency=None):
        store = get_store_class_by_name(store_class_name)
        return store.discover_urls_for_product_types(
            product_types, async, extra_args, queue, discover_urls_concurrency)

    @staticmethod
    @shared_task
    def products_for_urls_task(store_class_name, urls_with_product_types=None,
                               async=True, extra_args=None, queue=None):
        store = get_store_class_by_name(store_class_name)
        return store.products_for_urls(urls_with_product_types, async,
                                       extra_args,
                                       queue)

    @staticmethod
    @shared_task
    def discover_urls_for_product_type_task(store_class_name, product_type,
                                            extra_args=None):
        store = get_store_class_by_name(store_class_name)
        logger.info('Discovering URLs')
        logger.info('Store: ' + store.__name__)
        logger.info('Product type: ' + product_type)
        discovered_urls = store.discover_urls_for_product_type(product_type,
                                                               extra_args)
        for idx, url in enumerate(discovered_urls):
            logger.info('{} - {}'.format(idx, url))
        return discovered_urls

    @staticmethod
    @shared_task
    def products_for_url_task(store_class_name, url, product_type=None,
                              extra_args=None):
        store = get_store_class_by_name(store_class_name)
        logger.info('Obtaining products for URL')
        logger.info('Store: ' + store.__name__)
        logger.info('Product type: ' + product_type)
        logger.info('URL: ' + url)
        raw_products = store.products_for_url(
            url, product_type, extra_args)

        serialized_products = [p.serialize() for p in raw_products]

        for idx, product in enumerate(serialized_products):
            logger.info('{} - {}'.format(idx, product))

        return serialized_products

    ##########################################################################
    # Implementation dependant methods
    ##########################################################################

    @classmethod
    def product_types(cls):
        raise NotImplementedError('This method must be implemented by '
                                  'subclasses of Store')

    @classmethod
    def products_for_url(cls, url, product_type=None, extra_args=None):
        raise NotImplementedError('This method must be implemented by '
                                  'subclasses of Store')

    @classmethod
    def discover_urls_for_product_type(cls, product_type, extra_args=None):
        raise NotImplementedError('This method must be implemented by '
                                  'subclasses of Store')

    ##########################################################################
    # Utility methods
    ##########################################################################

    @classmethod
    def create_celery_group(cls, tasks):
        # REF: https://stackoverflow.com/questions/41371933/why-is-this-
        # construction-of-a-group-of-chains-causing-an-exception-in-celery
        if len(tasks) == 1:
            g = group(tasks)()
        else:
            g = group(*tasks)()
        return g
