from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time


class Scraper:

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
        self.driver = webdriver.Chrome()
        search_url = 'https://pitchup.com'
        self.driver.get(search_url)
        self.campsite_links = []
        self.page_num = 0

    def open_england_search(self):
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
        box = self.driver.find_element(By.ID, id)
        box.click()
        if content:
            box.send_keys(content)

    def set_search_criteria(self, criteria):
        for key, value in criteria.items():
            id_for_key = Scraper.field_ids[key]
            if type(id_for_key) == str:
                self.enter_data_into_box(id_for_key, value)
            else:
                # id_for_key is a dict of ids
                # the keys of id_for_key will match the contents of the list value
                for k in value:
                    self.enter_data_into_box(id_for_key[k])
            
    def kickoff_search(self):
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


    def grab_links_from_page(self):
        td_list = self.driver.find_elements(By.CLASS_NAME, 'campsite-name')
        self.campsite_links.extend([{'name': td.text, 'link': td.get_attribute('href')} for td in td_list if td.text != ''])

    def scrape_pages(self):
        # do the current page
        self.page_num += 1
        print(f'scraping page {self.page_num}...')
        self.grab_links_from_page()
        # then scrape the next one
        next_prev_page = self.driver.find_elements(By.CLASS_NAME, 'prevnext')
        next_page = [p.get_attribute('href') for p in next_prev_page if p.text.startswith('Next')]
        if not next_page:
            return
        self.driver.get(next_page[0])
        time.sleep(1)
        self.scrape_pages()


if __name__ == "__main__":
    scraper = Scraper()
    scraper.open_england_search()
    scraper.set_search_criteria({'keywords':'west sussex', 'types': ['tent','caravan']})
    scraper.kickoff_search()
    scraper.scrape_pages()
    print(scraper.campsite_links)
    print(f'Found a total of {len(scraper.campsite_links)} sites.')