# Data-Collection-Pipeline-project

**Scraper** is a Python library for scraping data from a campsite website.
This is the second project in AiCore - a webscraper based on Selenium. I've chosen to get campsite data as my test case, from [pitchup.com](https://pitchup.com/campsites/England).

Relies on local copy of AWS credentials and access to the bucket (as configure near the top of the file).

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install:

```bash
pip install -r requirements.txt
```

The latest version of this system will eventually be automatically pushed to Docker hub as stratovate/scraper

## Usage

```python
python campsite_scraper.py
```

If you want to change the number of sites scraped, you'll need to edit the source code. This isn't great, and is something I ought to change based on arguments passed to the Docker container when it's run.

## Contributing
No point contributing. This is just a learning project.

## License
[MIT](https://choosealicense.com/licenses/mit/)