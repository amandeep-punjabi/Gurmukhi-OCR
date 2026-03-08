import os
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog
import re

# Paths for folders
base_dir = "D:/Python/PunjabiOCR"
corpus_folder = os.path.join(base_dir, "corpus")
corrections_folder = os.path.join(base_dir, "corrections")

# Initialize Punjabi corpus
punjabi_corpus = []

def create_directories():
    # Create the necessary directories if they don't already exist
    for folder in [base_dir, corpus_folder, corrections_folder]:
        if not os.path.exists(folder):
            os.makedirs(folder)

def process_user_images(image_path):
    if image_path.endswith(('.png', '.jpg')):
        image = Image.open(image_path)

        extracted_text = pytesseract.image_to_string(image, lang='pan')

        punjabi_corpus.append(extracted_text)

def process_user_pdfs(pdf_path):
    if pdf_path.endswith('.pdf'):
        print("Processing PDF:", pdf_path)
        pdf_document = fitz.open(pdf_path)

        pdf_text = ''
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            pdf_text += page.get_text()

        extracted_text = pytesseract.image_to_string(pdf_text, lang='pan')

        punjabi_corpus.append(extracted_text)

def extract_english_and_numerals(text):
    english_and_numerals = re.findall(r'[\w\d]+', text)
    return ' '.join(english_and_numerals)

def review_and_correct_text(ocr_text):
    # Create a user-friendly interface for reviewing and correcting text
    # You can use a GUI library like Tkinter to create a review and correction window
    # Allow the user to make corrections and save the corrected text
    pass  # Placeholder code

def train_tesseract_with_corpus():
    # Implement the training process for Tesseract using the updated corpus
    # You can use the 'lstmtraining' command as described in previous responses
    pass  # Placeholder code

def main():
    create_directories()

    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename()

    if not file_path:
        print("No file selected. Exiting.")
        return

    if os.path.isfile(file_path):
        if file_path.endswith(('.png', '.jpg')):
            process_user_images(file_path)
        elif file_path.endswith('.pdf'):
            process_user_pdfs(file_path)

        ocr_text = '\n'.join(punjabi_corpus)
        with open('user_ocr_output.txt', 'w', encoding='utf-8') as output_file:
            output_file.write(ocr_text)

        extracted_english_numerals = extract_english_and_numerals(ocr_text)
        print("Extracted English and Numerals:", extracted_english_numerals)

        review_and_correct_text(ocr_text)

    elif os.path.isdir(file_path):
        for filename in os.listdir(file_path):
            file_path = os.path.join(file_path, filename)
            if filename.endswith(('.png', '.jpg')):
                process_user_images(file_path)
            elif filename.endswith('.pdf'):
                process_user_pdfs(file_path)

        ocr_text = '\n'.join(punjabi_corpus)
        with open('user_ocr_output.txt', 'w', encoding='utf-8') as output_file:
            output_file.write(ocr_text)

        extracted_english_numerals = extract_english_and_numerals(ocr_text)
        print("Extracted English and Numerals:", extracted_english_numerals)

        review_and_correct_text(ocr_text)

    train_tesseract_with_corpus()

if __name__ == "__main__":
    main()
