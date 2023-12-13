import argparse
from datetime import datetime
import json
import os
import re
import time
from urllib.request import urlopen
from urllib.error import HTTPError
import bs4
import pandas as pd
from collections import Counter
import regex as re
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, ElementClickInterceptedException, ElementNotVisibleException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

########### UTILITY FUNCTIONS TO SCRAPE BOOK PAGE FOR BOOK INFORMATION AND REVIEWS ###########

def get_dates(user_id,page):
    url = 'https://www.goodreads.com/review/list/' + user_id + '?page=' + page + '&shelf=read' + '&sort=date_read'
    print(url)
    #https://www.goodreads.com/review/list/130188909?page=2&shelf=read
    # source = driver.page_source
    # '&sort=date_read'
    source = urlopen(url)
    soup = bs4.BeautifulSoup(source, 'html.parser')
    dates = []
    date_start = soup.find_all('span', {'class': 'date_started_value'},limit=None)
    if date_start:
        for node in date_start:
            dates.append(node.text)
        return dates
    else:
        return ""
    
def get_all_lists(bookid, soup):

    lists_url = '/list/book/' + bookid
    
    lists = []
    list_count_dict = {}
   
     # Open lists url
    source = urlopen('https://www.goodreads.com' + lists_url)
    soup = bs4.BeautifulSoup(source, 'lxml')
    lists += [' '.join(node.text.strip().split()) for node in soup.find_all('div', {'class': 'cell'})]

    i = 0
    while soup.find('a', {'class': 'next_page'}) and i <= 10:

        time.sleep(2)
        next_url = 'https://www.goodreads.com' + soup.find('a', {'class': 'next_page'})['href']
        source = urlopen(next_url)
        soup = bs4.BeautifulSoup(source, 'lxml')

        lists += [node.text for node in soup.find_all('div', {'class': 'cell'})]
        i += 1

    # Format lists text.
    for _list in lists:
        _list_name = _list.split()[:-2][0]
        _list_count = int(_list.split()[-2].replace(',', ''))
        list_count_dict[_list_name] = _list_count

    return list_count_dict

def get_genres(soup):
    genres = []
    # Find genre labels
    for node in soup.find_all('span', {'class': 'BookPageMetadataSection__genreButton'}):
        current_genres = node.find('span', {'class': 'Button__labelItem'})
        genres.append(current_genres.text)

    return genres

def get_rating_distribution(soup):
    fiveStar = soup.find('div', {'data-testid': 'labelTotal-5'}).text
    fourStar = soup.find('div', {'data-testid': 'labelTotal-4'}).text
    threeStar = soup.find('div', {'data-testid': 'labelTotal-3'}).text
    twoStar = soup.find('div', {'data-testid': 'labelTotal-2'}).text
    oneStar = soup.find('div', {'data-testid': 'labelTotal-1'}).text
    distribution_dict = {'5 Stars': fiveStar,
                         '4 Stars': fourStar,
                         '3 Stars': threeStar,
                         '2 Stars': twoStar,
                         '1 Star':  oneStar}
    return distribution_dict

def get_summary(soup):
    summary = soup.find('div', {'data-testid': 'description'}, {'class': 'Formatted'}).text
    return summary

def get_cover_image_uri(soup):
    series = soup.find('div', {'class': 'BookCover__image'})
    
    if series:
        series_uri = series.find('img', {"class": "ResponsiveImage"})
        return series_uri['src']
    else:
        return ""
    
def get_rating(node):
    row = node.find('div', {'class': 'ShelfStatus'})
    rating = row.find_all('aria-label'==True)[0]
    return rating.get('aria-label')
    #return RATING_STARS_DICT[rating.get('aria-label')]


def get_user_name(node):
    if len(node.find('div', {'data-testid': 'name'}, {'class': 'ReviewerProfile__name'})) > 0:
        return node.find('div', {'data-testid': 'name'}, {'class': 'ReviewerProfile__name'}).text
    return ''

def get_user_url(node):
    if len(node.find('div', {'data-testid': 'name'}, {'class': 'ReviewerProfile__name'})) > 0:
        return node.find('div', {'data-testid': 'name'}, {'class': 'ReviewerProfile__name'})[0]['href']
    return ''


def get_date(node):
    if len(node.find('section', {'class': 'ReviewCard__row'})) > 0:
        row = node.find('section', {'class': 'ReviewCard__row'})
        return row.text
    return ''


def get_text(node):

    full_text = ''

    if len(node.find('div', {'class': 'TruncatedContent'})) > 0:

        content = node.find('div', {'class': 'TruncatedContent'})
        full_text = content.find('span', {'class': 'Formatted'}).text
        

    return full_text

def get_id(bookid):
    pattern = re.compile("([^.]+)")
    return pattern.search(bookid).group()

def scrape_reviews_on_current_page(driver, book_id):
    reviews = []

    # Pull page source, load into BeautifulSoup, and find all review nodes.

    source = driver.page_source
    soup = bs4.BeautifulSoup(source, 'html.parser')
    nodes = soup.find_all('article', {'class': 'ReviewCard'})
    # nodes = soup.find_all('div', {'class': 'review'})
    # book_title = soup.find(id='bookTitle').text.strip()
    
    # Iterate through and parse the reviews.
    for node in nodes:
        reviews.append({#'book_id_title': book_id,
                        # 'book_id': get_id(book_id),
                        # 'review_id': review_id, 
                        'date': get_date(node), 
                        'rating': get_rating(node), 
                        'user_name': get_user_name(node),
                        'text': get_text(node)})

    return reviews

def get_reviews_few_pages(book_id):

    reviews = []
    url = 'https://www.goodreads.com/book/show/' + book_id + '/reviews'
    driver = webdriver.Safari()
    driver.get(url)
    source = driver.page_source

    try:
        time.sleep(4)
    
        # Scrape the first page of reviews.
        reviews = scrape_reviews_on_current_page(driver, book_id)
        print('Scraped page 1')
        # Clicks through each of the following pages and scrape each page.
        page_counter = 2
        while page_counter <=3:
            try:
                if driver.find_element(By.CSS_SELECTOR, 'span[data-testid="loadMore"]'):
                    button = driver.find_element(By.CSS_SELECTOR,'span[data-testid="loadMore"]')

                    driver.execute_script("arguments[0].scrollIntoView();", button)

                    wait = WebDriverWait(driver, 10)
                    button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'span[data-testid="loadMore"]')))
                    driver.execute_script("arguments[0].click();", button)

                    time.sleep(3)
                    
                    reviews = scrape_reviews_on_current_page(driver, book_id)
                    print(f"Scraped page {page_counter}")
                    page_counter += 1
                else:
                    return reviews
            
            except NoSuchElementException:
                if page_counter == 3:
                    try:
                        driver.find_element(By.LINK_TEXT, str(9)).click()
                        time.sleep(2)
                        continue
                    except:
                        return reviews
                else:
                    print(f'{book_id} has less than 3 pages of reviews!')
                    return reviews
            
            except ElementNotVisibleException:
                print('ERROR ElementNotVisibleException: Pop-up detected, reloading the page.')
                reviews = get_reviews_few_pages( book_id)
                return reviews
                        
            except ElementClickInterceptedException:
                print(f'🚨 ElementClickInterceptedException (Likely a pop-up)🚨\n🔄 Refreshing Goodreads site and skipping problem page {page_counter}🔄')
                driver.get(url)
                time.sleep(3)
                page_counter += 1
                continue
                
            except StaleElementReferenceException:
                print('ERROR: StaleElementReferenceException\nRefreshing Goodreads site and skipping problem page {page_counter} ')
                driver.get(url)
                time.sleep(3)
                page_counter += 1
                continue
                
    except ElementClickInterceptedException:
                print(f'🚨 ElementClickInterceptedException (Likely a pop-up)🚨\n🔄 Refreshing Goodreads site and rescraping book🔄')
                driver.get(url)
                time.sleep(3)
                reviews = get_reviews_few_pages(book_id)
                return reviews
                
    except ElementNotInteractableException:
            print('🚨 ElementNotInteractableException🚨 \n🔄 Refreshing Goodreads site and rescraping book🔄')
            reviews = get_reviews_few_pages(book_id)
            driver.quit()
            return reviews

    return reviews

    
def scrape_book(book_id):
    url = 'https://www.goodreads.com/book/show/' + book_id


    source = urlopen(url)
    soup = bs4.BeautifulSoup(source, 'html.parser')

    time.sleep(2)
    
    return {'book_id_title':        book_id,
            'book_title':           ' '.join(soup.find('h1', {'data-testid': 'bookTitle'}).text.split()),
            'summary':              get_summary(soup),
            'cover_image_uri':      get_cover_image_uri(soup),
            'genres':               get_genres(soup),
            'lists':                get_all_lists(book_id, soup),
            'num_ratings':          soup.find('span', {'data-testid': 'ratingsCount'}).contents[0],
            'num_reviews':          soup.find('span', {'data-testid': 'reviewsCount'}).contents[0],
            'rating_distribution':  get_rating_distribution(soup),
            'reviews':              get_reviews_few_pages(book_id)}
