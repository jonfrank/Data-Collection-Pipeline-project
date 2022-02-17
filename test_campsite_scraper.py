import unittest
from campsite_scraper import Scraper
import selenium
import os

class ScraperTest(unittest.TestCase):
    def setUp(self):
        self.scraper = Scraper()

    def test_scraper_init(self):
        self.assertEqual(type(self.scraper.driver), selenium.webdriver.chrome.webdriver.WebDriver)

    def test_open_england_search(self):
        self.scraper.open_england_search()
        self.assertEqual(self.scraper.driver.current_url, 'https://www.pitchup.com/campsites/England/')

    # def test_search_with_criteria(self):
    #     self.scraper.open_england_search()
    #     self.scraper.search_with_criteria({'keywords':'west sussex', 'types': ['tent','caravan']})
    #     # what to test here?
    #     pass

    def test_scrape_pages(self):
        self.scraper.open_england_search()
        self.scraper.search_with_criteria({'keywords':'west sussex', 'types': ['tent','caravan']})
        self.scraper.scrape_pages(test_mode=True)
        self.assertGreaterEqual(len(self.scraper.campsite_links), 1)

    def test_save_all_campsite_data(self):
        self.scraper.open_england_search()
        self.scraper.search_with_criteria({'keywords':'west sussex', 'types': ['tent','caravan']})
        self.scraper.scrape_pages(test_mode=True)
        self.scraper.save_all_campsite_data()
        self.assertTrue(os.path.exists(self.scraper.storage_folder))

unittest.main(argv=[''], verbosity=2, exit=False)