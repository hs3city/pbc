# -*- coding: utf-8 -*-

import logging
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
from urllib.request import urlretrieve

from utils import db_connection


logger = logging.getLogger()


class GifDownloader(object):

    """
    Downloads latest gif from the pankreator.org site.
    """

    def __init__(self, config, db):
        self.config = config
        self.db = db

    def extract_data_from_page(self):
        """
        Parse the site html.
        # TODO: this should be replaced with API call when site supports it.
        """
        results = []
        logger.info("Connecting to {}".format(self.config['default']['pankreator_site']))
        r = requests.get(self.config['default']['pankreator_site'], verify=False)
        logger.info("Connected to {}".format(self.config['default']['pankreator_site']))
        soup = BeautifulSoup(r.text, 'lxml')
        posts = [a for a in soup.findAll('div', attrs={'class': 'span2'})]
        for p in posts:
            post = {}
            figcaption = p.find('figcaption', {'class': 'gify'})
            figure = p.find('div', {'class': 'item-image'})
            post['title'] = figcaption.a.getText().replace('\t', '').replace('\n', '')
            post['gif_url'] = urljoin(self.config['default']['pankreator_site'],
                                      figure.a.img['src'])
            post['url'] = urljoin(self.config['default']['pankreator_site'],
                                  figure.a['href'])
            results.append(post)
        return results

    def extract_data_from_api(self):
        results = []
        response = requests.get("http://pankreator.org/wp-json/pankreator/postcards?filter[per_page]=100&page=1")
        for card in response.json():
            post = {}
            post['title'] = card['title']['rendered']
            if card['better_featured_image'] is None:
                continue
            post['gif_url'] = card['better_featured_image']['source_url']
            post['url'] = card['link']
            results.append(post)
        return results

    def download_image(self, url):
        urlretrieve(url, self.config['files']['gif_path'])
        return self.config['files']['gif_path']

    @staticmethod
    def compare_results(db_results, web_results):
        web_gifs = [w['gif_url'] for w in web_results]
        db_gifs = [d[3] for d in db_results if d]
        return set(web_gifs) - set(db_gifs)

    def check_new_posts(self):
        """
        Something that was found on the site, but wasn't added to the db yet.
        """
        #results = self.extract_data_from_page()
        results = self.extract_data_from_api()
        if not results:
            return None, None
        with db_connection(self.db) as cursor:
            cursor.execute('select * from pankreator_gifs order by id asc')

            differences = self.compare_results(cursor.fetchall(), results)

            if differences:
                for item in results:
                    if item['gif_url'] in differences:
                        new_item = item
                        logger.info('Something new! %s' % new_item['title'].decode('utf-8'))
                        return self.download_image(new_item['gif_url']), new_item
        return None, None
