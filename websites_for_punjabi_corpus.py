from googlesearch import search
import os
import requests
from bs4 import BeautifulSoup
import re
import time
import random

# Define the queries for Punjabi newspaper websites and other Punjabi websites
newspaper_query = "Punjabi newspaper websites"
website_query = "Punjabi websites"

# Define the number of search results to retrieve for each query
num_results = 20

# Create a list to store the search results
newspaper_results = []
website_results = []

# Function to perform a search and filter out duplicate URLs
def search_and_filter(query, results_list):
    search_results = [result for result in search(query, num_results=num_results, lang="pa")]
    return list(set(search_results) - set(results_list))

# Perform the searches
newspaper_results = search_and_filter(newspaper_query, newspaper_results)
website_results = search_and_filter(website_query, website_results)

# Define the folder and file path to save the URLs
folder_path = "D:/Python/PunjabiOCR/punjabi_websites"
os.makedirs(folder_path, exist_ok=True)
file_path = os.path.join(folder_path, "urls.txt")

# Load existing URLs from the file if it exists
existing_urls = []

if os.path.isfile(file_path):
    with open(file_path, "r") as file:
        existing_urls = [line.strip() for line in file.readlines()]

# Filter out existing URLs
new_urls = list(set(newspaper_results + website_results) - set(existing_urls))

if new_urls:
    # Append the new URLs to the existing file
    with open(file_path, "a") as file:
        file.write("\n".join(new_urls) + "\n")
    print(f"New URLs added to: {file_path}")
else:
    print("No new URLs found.")

# Define the folder for Punjabi corpus
corpus_folder = "D:/Python/PunjabiOCR/punjabi_corpus"
os.makedirs(corpus_folder, exist_ok=True)

# Function to scrape Punjabi words from a URL and return the unique words
def scrape_punjabi_words(url, page_number):
    punjabi_words = []
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Adjusted regular expression to capture Punjabi words and common punctuation
        punjabi_words = list(set(re.findall(r'[\u0A00-\u0A7F]+', soup.get_text())))
    except requests.exceptions.RequestException as e:
        print(f"HTTP error while scraping from {url}: {str(e)}")
    except Exception as e:
        print(f"Error while scraping from {url}: {str(e)}")
    print(f"Scraped page {page_number} - URL: {url}")
    print(f"Word count from page {page_number}: {len(punjabi_words)}")
    return punjabi_words

# Function to add new words to the corpus file
def add_words_to_corpus(corpus_file_path, punjabi_words):
    new_word_count = len(punjabi_words)
    total_word_count = 0
    if os.path.isfile(corpus_file_path):
        with open(corpus_file_path, "a", encoding="utf-8") as file:
            # Write the scraped Punjabi words to the file
            file.write("\n".join(punjabi_words) + "\n")
        with open(corpus_file_path, "r", encoding="utf-8") as file:
            total_word_count = len(file.readlines())
    return new_word_count, total_word_count

# Accumulate Punjabi words from all URLs
all_punjabi_words = []
total_added_words = 0  # Total words added in this iteration
total_corpus_words = 0  # Total words in the corpus file

# Track the pages that have already been scraped
scraped_pages = set()

for page_number, url in enumerate(existing_urls, start=1):
    if url in scraped_pages:
        continue  # Skip already scraped pages

    punjabi_words = scrape_punjabi_words(url, page_number)
    all_punjabi_words.extend(punjabi_words)
    scraped_pages.add(url)  # Add the scraped page to the set

    if punjabi_words:
        corpus_file_path = os.path.join(corpus_folder, "punjabi_corpus.txt")
        new_word_count, total_word_count = add_words_to_corpus(corpus_file_path, punjabi_words)
        total_added_words += new_word_count
        total_corpus_words = total_word_count

        print(f"{new_word_count} new Punjabi words added in this iteration.")
        print(f"Total Punjabi words in the corpus: {total_corpus_words}")

    sleep_duration = random.uniform(2, 6)
    time.sleep(sleep_duration)

print(f"Total words added in this iteration: {total_added_words}")
print(f"Total Punjabi wordsin the corpus at the end of the scraping: {total_corpus_words}")