# Data-Collection-Pipeline-project

This is the second project in AiCore - a webscraper based on Selenium. I've chosen to get campsite data as my test case, from [pitchup.com](https://pitchup.com/campsites/England).

This implementation was for retrieving charity data from the Charity Commission, but I've changed tack and it needs rewriting for the campsite data.

Currently though (for charities) it takes hard-coded (but easily modified) search parameters, performs an advanced search, and then scrapes all the charity numbers returned in the search. The full URL for each charity page is formed when the list of links is requested from the `Scraper` instance.
