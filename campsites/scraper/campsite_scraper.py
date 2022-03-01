from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
import time
from urllib.parse import urlparse
import urllib.request
import uuid
import os
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
import pandas as pd
import psycopg2
import sqlalchemy
from tqdm import tqdm
import pprint
pp = pprint.PrettyPrinter(indent=4)


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

    def __init__(self, campsite_count=0):
        """Initialise the scraper, creating local storage folder ./raw_data if it doesn't already exist."""
        chrome_options = Options()
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,180")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        search_url = 'https://pitchup.com'
        self.driver.get(search_url)
        self.campsite_links = []
        self.page_num = 0
        # create folder if it doesn't yet exist
        self.storage_folder = './raw_data'
        Scraper.__create_folder_if_not_exists(self.storage_folder)
        # urllib user-agent seems to be blocked by the image source (returns 403)
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.81 Safari/537.36')]
        urllib.request.install_opener(opener)
        # Set up AWS clients
        session = boto3.Session()
        self.s3 = session.resource('s3')
        self.rds_client = session.client('rds')
        self.bucket = 'aicore-jf-campsite2-bucket'
        self.rds_params = {
            "host": "campsite-db2.cv8wi4qhb3tj.eu-west-2.rds.amazonaws.com",
            "port": "5432",
            "user": "postgres",
            # "region":"eu-west-2",
            "database": "campsites",
            "password": "pennine1"
        }
        self.campsite_count = campsite_count
        self.metrics = {'new': 0, 'repeat': 0}
        self.cursor = None
        self.campsite_data = []

    def __create_folder_if_not_exists(f):
        """Create the specified folder if it doesn't already exist. Class method."""
        if not os.path.exists(f):
            os.makedirs(f)

    def __clear_local_folder(self):
        [f.unlink() for f in Path(self.storage_folder).glob('*') if f.is_file()]

    def __rds_connect(self):
        self.conn = None
        try:
            print('Connecting to PostgreSQL / RDS...')
            self.conn = psycopg2.connect(sslmode='require', sslrootcert="./global-bundle.pem", **self.rds_params)
            print('Connected OK - now trying to create the engine')
            self.engine = sqlalchemy.create_engine(f"postgresql+psycopg2://{self.rds_params['user']}:{self.rds_params['password']}@{self.rds_params['host']}:{self.rds_params['port']}/{self.rds_params['database']}")
            print('Created sqlalchemy engine')
        except (Exception, psycopg2.DatabaseError) as error:
            print(f"Error connecting to RDS: {error}")

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
    
    def __enter_data_into_box(self, id, content=None):
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
            if type(id_for_key) is str:
                self.__enter_data_into_box(id_for_key, value)
            else:
                # id_for_key is a dict of ids
                # the keys of id_for_key will match the contents of the list value
                for k in value:
                    self.__enter_data_into_box(id_for_key[k])
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

    def _grab_links_from_search_results_page(self):
        """Add to the scraper's list of campsites all those showing on the current search page.
        
        Result:
            Number of links scraped from the current page.
        """
        td_list = self.driver.find_elements(By.CLASS_NAME, 'campsite-name')
        self.campsite_links.extend([{
                'name': td.text, 
                'url': td.get_attribute('href'),
                'id': urlparse(td.get_attribute('href')).path.strip('/').replace('/', '-'),
                'uuid': str(uuid.uuid4())
            } for td in td_list if td.text != ''])

    def scrape_pages(self, test_mode=False):
        """Scrape search result pages for campsite names, ids and links.
        Recursive: call this method while on the first page, and it will crawl until there are no more pages available.
        """
        self.page_num += 1
        print(f'scraping page {self.page_num}... ({len(self.campsite_links)} sites so far)')
        # do the current page
        self._grab_links_from_search_results_page()
        # then scrape the next one
        next_prev_page = self.driver.find_elements(By.XPATH, '//*[@class="paging"]//a[contains(@class,"prevnext")]')
        next_page = [p.get_attribute('href') for p in next_prev_page if p.text.startswith('Next')]
        if test_mode or not next_page or len(self.campsite_links) >= self.campsite_count:
            # print(f"Scraped details for {len(self.campsite_links)} campsites.")
            # pp.pprint(self.campsite_links)
            return
        print(f"Finished page {self.page_num} - now going to {next_page[0]}")
        self.driver.get(next_page[0])
        time.sleep(1)
        # recursion
        self.scrape_pages()

    def _retrieve_specific_campsite_data(self, campsite):
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
        try:
            header = self.driver.find_element(By.CLASS_NAME, 'campsite-header')
            details['sitename'] = header.find_element(By.TAG_NAME, 'h1').text
        except:
            return None
        try: 
            details['rating'] = header.find_element(By.CLASS_NAME, 'rating_value').text.strip('')
        except:
            details['rating'] = ''
        try:
            details['date_open'] = header.find_element(By.CLASS_NAME, 'next-open-date').get_attribute('data-next-open-date')
        except:
            details['date_open'] = ''
        try:
            pricing = self.driver.find_element(By.CLASS_NAME, 'headlineprice')
            details['price_from'] = pricing.find_element(By.CLASS_NAME, 'money-GBP').text.strip('£')
        except:
            details['price_from'] = ''
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
            details['images'] = [None]
        details['uuid'] = campsite['uuid']
        details['id'] = campsite['id']
        return details

    def save_specific_campsite_data(self, campsite):
        """Save details and images for a specific campsite. Called by save_all_campsite_data() method.

        Arguments:
        campsite - a dict (an element of the list generated by the scraper from search result pages) which includes the key 'url'
        """
        sql_select = f"SELECT uuid FROM campsites WHERE id=%s"
        details = self._retrieve_specific_campsite_data(campsite)
        if details==None:
            return
        # upload to RDS
        self.cursor = self.conn.cursor()
        try:
            # check if it's already in RDS
            self.cursor.execute(sql_select, (details['id'],))
        except (Exception, psycopg2.Error) as error:
            print(f"Failed (on {details['id']}) with SQL SELECT check: ", error)
        matching_rows = self.cursor.fetchall()
        if len(matching_rows) == 0:
            self.metrics['new'] += 1
            # self._write_campsite_to_rds(details)
            self._add_campsite_to_data_list(details)
        else:
            self.metrics['repeat'] += 1
        self.cursor.close()
        # write images to temp local file storage
        if len(matching_rows) == 0:
            #  go right ahead if we didn't find this campsite already in RDS - we know that the images won't be there
            self._retrieve_and_upload_images(details)
        else:
            try:
                # check if first image already exists in s3
                self.s3.meta.client.head_object(Bucket=self.bucket, Key=f"{matching_rows[0][0]}-0.jpg")
            except ClientError:
                # key not found, so we'll upload them 
                if details['images']:
                    self._retrieve_and_upload_images(details)

    # def _write_campsite_to_rds(self, details):
    #     """Write tabular data for a particular campsite to RDS.
        
    #     Arguments:
    #     details - a dict of the campsite attributes scraped from the website page
    #     """
    #     details_for_df = details.copy()
    #     del details_for_df['images']
    #     details_for_df['bullets'] = ' / '.join(details_for_df['bullets'])
    #     campsite_df = pd.DataFrame([details_for_df])
    #     column_values = tuple(campsite_df.to_numpy()[0])
    #     cols = ','.join(list(campsite_df.columns))
    #     value_placeholders = ','.join(['%s'] * len(list(campsite_df.columns)))
    #     insert_query = "INSERT INTO campsites ({}) VALUES ({})".format(cols, value_placeholders)
    #     self.cursor.execute(insert_query, column_values)
    #     self.conn.commit()  
        
    def _add_campsite_to_data_list(self, details):
        """Prepare tabular data for a particular campsite to be written to RDS later as a complete batch.
        
        Arguments:
        details - a dict of the campsite attributes scraped from the website page
        """
        details_for_df = details.copy()
        del details_for_df['images']
        details_for_df['bullets'] = ' / '.join(details_for_df['bullets'])
        self.campsite_data.append(details_for_df)

    def _write_all_campsites_to_rds(self):
        details_for_rds = pd.DataFrame(self.campsite_data)
        details_for_rds.to_sql('campsites', self.engine, if_exists='append')

    def _retrieve_and_upload_images(self, details):
        """Retrieve key images for a given campsite and send them to S3."""
        # clear folder before we start
        self.__clear_local_folder()
        for idx, img in enumerate(details['images']):
            time.sleep(1)
            urllib.request.urlretrieve(img, os.path.join(self.storage_folder, f"{idx}.jpg"))
        # upload them to S3
        for filename in os.listdir(self.storage_folder):
            try:
                response = self.s3.meta.client.upload_file(os.path.join(self.storage_folder, filename), self.bucket, f"{details['uuid']}-{filename}")
            except ClientError as e:
                print(f"Error uploading image {filename} for {details['uuid']}: {e}")


    def save_all_campsite_data(self):
        """Iterate through all campsites found in search, and save details and images to cloud (json) and local filesystem (images)."""
        saved_count = 0
        self.__rds_connect()
        self.progress = tqdm(total=self.campsite_count)
        for campsite in self.campsite_links:
            # print(f"Saving details for {campsite['name']}...")
            self.save_specific_campsite_data(campsite)
            saved_count += 1
            self.progress.update(1)
            if (saved_count == self.campsite_count):
                break
        self._write_all_campsites_to_rds()
        self.progress.close()

if __name__ == "__main__":
    print('Welcome to the campsite scraper!')
    scraper = Scraper(campsite_count=100)
    print('Opening England')
    scraper.open_england_search()
    print('Searching')
    scraper.search_with_criteria({'types': ['tent','caravan']})
    print('Scraping top level')
    scraper.scrape_pages(test_mode=False)
    print('Getting details')
    scraper.save_all_campsite_data()
    print('\r\n\n')
    print(f"Out of {len(scraper.campsite_links)}, {scraper.metrics['new']} were new and {scraper.metrics['repeat']} already known.")
    print('Finished.')
