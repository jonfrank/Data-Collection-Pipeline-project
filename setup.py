from setuptools import setup
from setuptools import find_packages

setup(
    name='campsite_scraper',
    version='0.16',
    description='Practice project for selenium and website scraping',
    url='https://github.com/jonfrank/Data-Collection-Pipeline-project',
    author='Jonathan Frank',
    license='MIT',
    packages=find_packages(),
    install_requires=['selenium','webdriver-manager','boto3','pandas','psycopg2','tqdm']
)