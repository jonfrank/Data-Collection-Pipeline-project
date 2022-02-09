from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time


class Scraper:

    field_ids = {
        'expenditure': {
            'min': '_uk_gov_ccew_portlet_CharitySearchPortlet_filterExpenditureFrom',
            'max': '_uk_gov_ccew_portlet_CharitySearchPortlet_filterExpenditureTo'
        },
        'charity_id': '_uk_gov_ccew_portlet_CharitySearchPortlet_keywords'
    }

    def __init__(self):
        self.driver = webdriver.Chrome()
        search_url = 'https://register-of-charities.charitycommission.gov.uk/charity-search'
        self.driver.get(search_url)
        # dismiss cookie banner if there is one
        try:
            cookie_accept_div = self.driver.find_element(
                By.ID, 'cookie-consent-banner')
            cookie_button_holder = cookie_accept_div.find_element(
                By.CLASS_NAME, 'button-holder')
            cookie_accept_button = cookie_button_holder.find_element(
                By.TAG_NAME, 'a')
            cookie_accept_button.click()
            time.sleep(0.5)
        except:
            pass
        self.charity_links = []
        self.open_advanced_search()

    def open_advanced_search(self):
        search_link = self.driver.find_element(By.ID, 'advanced-search-link')
        search_link.click()
        delay = 5
        try:
            WebDriverWait(self.driver, delay).until(EC.presence_of_element_located(
                (By.ID, '_uk_gov_ccew_portlet_CharitySearchPortlet_keywords')))
            time.sleep(1)
        except TimeoutException:
            print("Timed out loading advanced search page")

    def enter_data_into_box(self, id, content):
        box = self.driver.find_element(By.ID, id)
        box.click()
        box.send_keys(content)

    def set_criteria(self, criteria):
        time.sleep(0.5)
        for key, value in criteria.items():
            id_for_key = Scraper.field_ids[key]
            # is it a straightforward string id?
            if type(id_for_key) == str:
                self.enter_data_into_box(id_for_key, value)
            else:
                # no, it's got min and max (or some other pairing)
                for key, id in id_for_key.items():
                    self.enter_data_into_box(id, value[key])
        time.sleep(0.5)

    def kickoff_search(self):
        time.sleep(1)
        search_button = self.driver.find_element(
            By.ID, '_uk_gov_ccew_portlet_CharitySearchPortlet_applyFilters')
        search_button.click()

    def grab_links_from_page(self):
        table_body = self.driver.find_element(By.XPATH, '//table[@data-searchcontainerid="_uk_gov_ccew_portlet_CharitySearchPortlet_search-result-entries"]/tbody')
        table_rows = table_body.find_elements(By.TAG_NAME, 'tr')
        td_list = [row.find_element(By.TAG_NAME, 'td') for row in table_rows]
        self.charity_links.extend([td.text for td in td_list if td.text != ''])

    def scrape_pages(self):
        # do the current page
        self.grab_links_from_page()
        # then scrape the next one
        next_page = self.driver.find_element(By.XPATH, '//span[@title="Next Page"]')
        next_page_href = next_page.find_element(By.XPATH, './..').get_attribute('href')
        if next_page_href.startswith('javascript'):
            return
        self.driver.get(next_page_href)
        time.sleep(1)
        self.scrape_pages()

if __name__ == "__main__":
    scraper = Scraper()
    scraper.set_criteria({  
                            # 'charity_id': '1127620',
                            'expenditure': {
                                'min': '9000000',
                                'max': '10000000'
                         }})

    scraper.kickoff_search()

    scraper.scrape_pages()
    print(scraper.charity_links)
