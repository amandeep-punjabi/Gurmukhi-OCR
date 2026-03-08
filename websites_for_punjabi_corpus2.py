import os
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import googlesearch as gs

def main():
    # Define the queries for Punjabi newspaper websites and other Punjabi websites
    newspaper_query = "Punjabi newspaper websites"
    website_query = "Punjabi websites"

    # Define the number of search results to retrieve for each query
    num_results = 40

    # Create a list to store the search results
    newspaper_results = []
    website_results = []

    # Function to perform a search and filter out duplicate URLs
    def search_and_filter(query, results_list):
        try:
            search_results = gs.search(query, num_results=num_results, lang="pa")
            results_list = list(set(search_results) - set(results_list))
        except requests.exceptions.HTTPError as e:
            # Handle the HTTP error, e.g., 429 (Too Many Requests)
            print(f"HTTP error: {e}")
        return results_list

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

    # Define the folder and file path for the Punjabi corpus
    corpus_folder = "D:/Python/PunjabiOCR/punjabi_corpus"
    corpus_file = "punjabi_corpus.txt"
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

    # Load existing corpus data
    existing_corpus = set()

    if os.path.isfile(os.path.join(corpus_folder, corpus_file)):
        with open(os.path.join(corpus_folder, corpus_file), "r", encoding="utf-8") as file:
            existing_corpus.update(line.strip() for line in file)

    # Function to clean and save Punjabi words to the corpus
    def save_to_corpus(punjabi_words):
        # Filter and clean Punjabi words
        punjabi_words = [word for word in punjabi_words if re.match(r'^[ਁ-ੴ\s]+$', word)]
        punjabi_words = set(punjabi_words)

        # Update the corpus with new words
        existing_corpus.update(punjabi_words)

        # Save the updated corpus
        with open(os.path.join(corpus_folder, corpus_file), "w", encoding="utf-8") as file:
            file.write("\n".join(existing_corpus))

    # Main scraping loop
    for url in existing_urls:
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract Punjabi words from the webpage
            punjabi_words = re.findall(r'[ਁ-ੴ]+', soup.get_text())

            # Save the Punjabi words to the corpus
            save_to_corpus(punjabi_words)

            # Print the number of new words added in this iteration
            print(f"{len(punjabi_words)} Words added from {url}")
        except Exception as e:
            print(f"Error scraping {url}: {e}")

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
            new_word_count, total_word_count = save_to_corpus(punjabi_words)
            total_added_words += new_word_count
            total_corpus_words = total_word_count

            print(f"{new_word_count} new Punjabi words added in this iteration.")
            print(f"Total Punjabi words in the corpus: {total_corpus_words}")


   # Sleep for a random duration between 2 to 5 seconds
    time.sleep(random.uniform(2, 5))

if __name__ == "__main__":
    main()
