from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from urllib.parse import urlparse
import urllib.request
import uuid
import os
import json

class Scraper:
    """Search the pitchup.com website and scrape details and images of each of the campsites returned."""
    field_ids = {
        'keywords': 'id_q',
        'types': {
            'tent': 'id_type_0',
            'caravan': 'id_type_1',
            'campervan': 'id_type_2',
            'lodge': 'id_type_3'
        }
    }

    def __init__(self):
        """Initialise the scraper, creating local storage folder ./raw_data if it doesn't already exist."""
        self.driver = webdriver.Chrome(ChromeDriverManager().install())
        search_url = 'https://pitchup.com'
        self.driver.get(search_url)
        self.campsite_links = []
        self.page_num = 0
        # create folder if it doesn't yet exist
        self.storage_folder = './raw_data'
        Scraper.create_folder_if_not_exists(self.storage_folder)
        # urllib user-agent seems to be blocked by the image source (returns 403)
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent','Mozilla/5.0 (Macintosh; Intel Mac OS X 12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.81 Safari/537.36')]
        urllib.request.install_opener(opener)

    def create_folder_if_not_exists(f):
        """Create the specified folder if it doesn't already exist. Class method."""
        if not os.path.exists(f):
            os.makedirs(f)

    def open_england_search(self):
        """Open the search page for campsites in England."""
        search_link = self.driver.find_element(By.ID, 'www-homepage-top-sites-image-england')
        self.driver.get(search_link.get_attribute('href'))
        delay = 5
        try:
            WebDriverWait(self.driver, delay).until(EC.presence_of_element_located(
                (By.ID, 'id_q')))
            time.sleep(1)
        except TimeoutException:
            print("Timed out loading England search page")
    
    def enter_data_into_box(self, id, content = None):
        """Put the given data into the input field with the specified id.
        If no content is supplied, the input element is assumed to be a checkbox, and is just clicked.
        """
        box = self.driver.find_element(By.ID, id)
        box.click()
        if content:
            box.send_keys(content)

    def search_with_criteria(self, criteria):
        """Fill in the search form with the given criteria, and then trigger the search.
        
        Arguments:
        criteria -- a dict of search criteria. Currently this can accept the following keys:
         - 'keyword', with a string value 
         - 'types', which is a list of types to search for, from ['tent','caravan','campervan','lodge']

        """
        for key, value in criteria.items():
            id_for_key = Scraper.field_ids[key]
            if type(id_for_key) == str:
                self.enter_data_into_box(id_for_key, value)
            else:
                # id_for_key is a dict of ids
                # the keys of id_for_key will match the contents of the list value
                for k in value:
                    self.enter_data_into_box(id_for_key[k])
        time.sleep(0.75)
        search_button = self.driver.find_element(By.CLASS_NAME, 'btn-update-search')
        search_button.click()
        delay = 5
        try:
            WebDriverWait(self.driver, delay).until(EC.presence_of_element_located(
                (By.ID, 'ajax__search-results-heading')))
            time.sleep(1)
        except TimeoutException:
            print("Timed out loading search results")


    def grab_links_from_search_results_page(self):
        """Add to the scraper's list of campsites all those showing on the current search page."""
        td_list = self.driver.find_elements(By.CLASS_NAME, 'campsite-name')
        self.campsite_links.extend([{
                'name': td.text, 
                'url': td.get_attribute('href'),
                'id': urlparse(td.get_attribute('href')).path.strip('/').replace('/','-'),
                'uuid': str(uuid.uuid4())
            } for td in td_list if td.text != ''])

    def scrape_pages(self):
        """Scrape search result pages for campsite names, ids and links.
        Recursive: call this method while on the first page, and it will crawl until there are no more pages available.
        """
        self.page_num += 1
        print(f'scraping page {self.page_num}...')
        # do the current page
        self.grab_links_from_search_results_page()
        # then scrape the next one
        next_prev_page = self.driver.find_elements(By.CLASS_NAME, 'prevnext')
        next_page = [p.get_attribute('href') for p in next_prev_page if p.text.startswith('Next')]
        if not next_page:
            return
        self.driver.get(next_page[0])
        time.sleep(1)
        # recursion
        self.scrape_pages()

    def retrieve_specific_campsite_data(self, campsite):
        """Get data and images for the chosen campsite. Called by save_specific_campsite_data() method.
        
        Arguments:
        campsite - a dict (an element of the list generated by the scraper from search result pages) which includes the key 'url'
        """
        self.driver.get(campsite['url'])
        delay = 5
        try:
            WebDriverWait(self.driver, delay).until(EC.presence_of_element_located(
                (By.CLASS_NAME, 'campsite-header')))
            time.sleep(1)
        except TimeoutException:
            print("Timed out loading details page")
        details = {}
        header = self.driver.find_element(By.CLASS_NAME, 'campsite-header')
        details['name'] = header.find_element(By.TAG_NAME, 'h1').text
        try: 
            details['rating'] = header.find_element(By.CLASS_NAME, 'rating_value').text.strip('')
        except:
            details['rating'] = ''
        try:
            details['next_open'] = header.find_element(By.CLASS_NAME, 'next-open-date').get_attribute('data-next-open-date')
        except:
            details['next_open'] = ''
        try:
            pricing = self.driver.find_element(By.CLASS_NAME, 'headlineprice')
            details['from_price_gbp'] = pricing.find_element(By.CLASS_NAME, 'money-GBP').text.strip('£')
        except:
            details['from_price_gbp'] = ''
        try:
            desc = self.driver.find_element(By.ID, 'campsite_description')
            details['description'] = desc.text
        except:
            details['description'] = ''
        try:
            bullet_list = desc.find_element(By.XPATH, './preceding-sibling::ul')
            details['bullets'] = [bullet.text for bullet in bullet_list.find_elements(By.TAG_NAME, 'li')]
        except:
            details['bullets'] = []
        try: 
            image_links = self.driver.find_elements(By.XPATH, '//*[contains(@class,"campsite-overview")]/table//img')
            # filter out links including h_30 because they're thumbnails
            details['images'] = [l.get_attribute('src') for l in image_links if 'h_30' not in l.get_attribute('src')]
        except:
            details['images'] = []
        details['uuid'] = campsite['uuid']
        details['id'] = campsite['id']
        return details

    def save_specific_campsite_data(self, campsite):
        """Save details and images for a specific campsite. Called by save_all_campsite_data() method.

        Arguments:
        campsite - a dict (an element of the list generated by the scraper from search result pages) which includes the key 'url'
        """
        details = self.retrieve_specific_campsite_data(campsite)
        campsite_file_folder = os.path.join(self.storage_folder, details['id'])
        Scraper.create_folder_if_not_exists(campsite_file_folder)
        campsite_file_path = os.path.join(campsite_file_folder, 'data.json')
        with open(campsite_file_path, 'w') as f:
            json.dump(details, f)
        if details['images']:
            image_folder = os.path.join(campsite_file_folder, 'images')
            Scraper.create_folder_if_not_exists(image_folder)
            for idx, img in enumerate(details['images']):
                time.sleep(1)
                urllib.request.urlretrieve(img, os.path.join(image_folder, f"{idx}.jpg"))

    def save_all_campsite_data(self):
        """Iterate through all campsites found in search, and save details and images to local filesystem."""
        for campsite in self.campsite_links:
            print(f"Saving details for {campsite['name']}...")
            self.save_specific_campsite_data(campsite)

if __name__ == "__main__":
    scraper = Scraper()
    scraper.open_england_search()
    scraper.search_with_criteria({'keywords':'west sussex', 'types': ['tent','caravan']})
    scraper.scrape_pages()
    scraper.save_all_campsite_data()
