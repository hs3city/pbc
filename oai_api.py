# -*- coding: utf-8 -*-

import logging
from random import randint
import re
import requests.exceptions
from sickle import Sickle
from utils import APIException


logger = logging.getLogger()

import warnings
import contextlib

import requests
from urllib3.exceptions import InsecureRequestWarning



old_merge_environment_settings = requests.Session.merge_environment_settings

@contextlib.contextmanager
def no_ssl_verification():
    opened_adapters = set()

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        # Verification happens only once per connection so we need to close
        # all the opened adapters once we're done. Otherwise, the effects of
        # verify=False persist beyond the end of this context manager.
        opened_adapters.add(self.get_adapter(url))

        settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
        settings['verify'] = False

        return settings

    requests.Session.merge_environment_settings = merge_environment_settings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InsecureRequestWarning)
            yield
    finally:
        requests.Session.merge_environment_settings = old_merge_environment_settings

        for adapter in opened_adapters:
            try:
                adapter.close()
            except:
                pass

class LibraryCrawler(object):

    """
    Perform a library scan over specific types of documents
    and return first matching record. Page from which the
    query starts is random.
    """

    def __init__(self, config, query):
        with no_ssl_verification():
            oai_api_url = config['default']['oai_api_url']
            self.sickle = Sickle(oai_api_url)
            self.resumption_token = self.get_token()

            # Queried attribute. I.e. type, description, format, subject, etc.
            self.query_dict = query

    def get_token(self):
        with no_ssl_verification():
            try:
                query = self.sickle.ListRecords(
                    metadataPrefix='oai_dc',
                    set='dLibraDigitalLibrar:PartnersResources:BGPAN'
                )
            except requests.exceptions.HTTPError as ex:
                message = "Couldn't connect to the library server! %s" % str(ex)
                logger.error(message)

                # Reraise the error to the main class.
                raise APIException(message)

            return query.resumption_token

    def query_itarator(self):
        with no_ssl_verification():
            length = self.resumption_token.complete_list_size
            rand_num = randint(20, int(length))
            new_token = re.sub(
                '_DL_LAST_ITEM_\d+_DL_', '_DL_LAST_ITEM_%d_DL_' % rand_num,
                self.resumption_token.token
            )
            return self.sickle.ListRecords(resumptionToken=new_token)

    @staticmethod
    def is_small_enough(description):
        try:
            for item in description:
                match = re.search(r"([0-9]+)\ss\.", item)
                if match:
                    pages = int(match.groups()[0])
                    if pages > 250:
                        return False

        except IndexError:
            pass
        return True

    def run(self):
        found = False
        iterator = self.query_itarator()
        while not found:
            record = iterator.next()
            for key, values in self.query_dict.items():
                try:
                    attribute = record.metadata[key]
                    description = record.metadata['description']
                    if attribute[0] in values and self.is_small_enough(description):
                        logger.info('Found something interesting!')
                        logger.info(record.metadata)
                        found = True
                        content_id = record.metadata['identifier'][1].lstrip('oai:pbc.gda.pl:')
                        return record, content_id
                except (KeyError, AttributeError):
                    pass
        return None, None
