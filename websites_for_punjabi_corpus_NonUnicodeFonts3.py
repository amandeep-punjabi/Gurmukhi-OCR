import os
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import pytesseract
from PIL import Image
from googlesearch import search
from tesseract import tesserocr

# Function to train Tesseract from downloaded fonts
def train_tesseract_with_fonts(fonts_folder):
    try:
        # Update the PATH variable to include Tesseract
        tesserocr.set_image_path("D:/Programs/Tesseract-OCR")

        # Check if 'tessdata' directory already exists
        tessdata_dir = os.path.join(fonts_folder, 'tessdata')
        if not os.path.exists(tessdata_dir):
            os.makedirs(tessdata_dir)

        # Train Tesseract with fonts
        for font_file in os.listdir(fonts_folder):
            if font_file.endswith('.ttf'):
                font_name = font_file.split('.ttf')[0]

                # Create training data and config files
                cmd = f"tesseract {fonts_folder}/{font_file} {tessdata_dir}/{font_name} --training_text {fonts_folder}/{font_name}.txt --outputbase {tessdata_dir}/{font_name} makebox"
                os.system(cmd)

                # Perform training
                os.system(f"combine_tessdata {tessdata_dir}/{font_name}.")

    except Exception as e:
        print(f"Error training Tesseract: {e}")

def main():
    # Train Tesseract from downloaded fonts
    train_tesseract_with_fonts("D:/Python/PunjabiOCR/downloaded_fonts")

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
        try:
            search_results = search(query, num_results=num_results, lang="pa")
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
            print(f"Words added in {url}: {len(punjabi_words)}")
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        
        # Sleep for a random duration between 2 to 5 seconds
        time.sleep(random.uniform(2, 5))

if __name__ == "__main__":
    main()
