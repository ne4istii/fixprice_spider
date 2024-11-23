# Fixprice Scrapy spider
Allows you to parse product catalog from a website and save the result to a json file.

## Stack
- Python 3.12
- Scrapy 2.11
- scrapy-rotating-proxies 0.6.2

## Installation
1. Install packages:  

>`pip install -r requirements.txt`

2. The input is the categories for parsing products, which must be filled in the file:

> `start_urls.txt`

3. If using a proxy - fill it in the list `proxies.txt`

4. Start `catalog` spider:  

>`scrapy crawl catalog -o results.json`

5. See result in `results.json`
