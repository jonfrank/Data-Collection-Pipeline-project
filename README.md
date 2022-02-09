# Data-Collection-Pipeline-project

This is the second project in AiCore - a webscraper based on Selenium. I've chosen to get charity data as my test case.

So far this implementation takes hard-coded (but easily modified) search parameters, performs an advanced search, and then scrapes all the charity numbers returned in the search. The full URL for each charity page is formed when the list of links is requested from the `Scraper` instance.
