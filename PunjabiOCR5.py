import os
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog
import re
import subprocess

# Paths for folders
base_dir = "D:/Python/PunjabiOCR"
corpus_folder = os.path.join(base_dir, "punjabi_corpus")
corrections_folder = os.path.join(base_dir, "corrections")
downloaded_fonts_folder = os.path.join(base_dir, "downloaded_fonts")

# Initialize Punjabi corpus
punjabi_corpus = []

def create_directories():
    # Create the necessary directories if they don't already exist
    for folder in [base_dir, corpus_folder, corrections_folder, downloaded_fonts_folder]:
        if not os.path.exists(folder):
            os.makedirs(folder)

def process_user_images(image_path):
    if image_path.endswith(('.gif', '.png', '.jpg', '.jpeg', '.jpg')):
        image = Image.open(image_path)

        # Use pytesseract with custom configuration to extract Punjabi, Hindi, and Sanskrit
        extracted_text = pytesseract.image_to_string(image, lang='pan+eng+hin+san', config='--psm 6 --oem 1')

        # Provide the user an opportunity to review and correct the text
        corrected_text = review_and_correct_text(extracted_text)

        # Save the corrected text to the corrections folder
        save_corrected_text(corrected_text)

        punjabi_corpus.append(corrected_text)

        print("Extracted Text:", extracted_text)

def process_user_pdfs(pdf_path):
    if pdf_path.endswith('.pdf'):
        pdf_document = fitz.open(pdf_path)

        pdf_text = ''
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            pdf_text += page.get_text()

        # Use pytesseract with custom configuration to extract Punjabi, Hindi, and Sanskrit
        extracted_text = pytesseract.image_to_string(pdf_text, lang='pan+eng+hin+san', config='--psm 6 --oem 1')

        # Provide the user an opportunity to review and correct the text
        corrected_text = review_and_correct_text(extracted_text)

        # Save the corrected text to the corrections folder
        save_corrected_text(corrected_text)

        punjabi_corpus.append(corrected_text)

        print("Extracted Text:", extracted_text)

def review_and_correct_text(ocr_text):
    # Create a user-friendly interface for reviewing and correcting text
    # You can use a GUI library like Tkinter to create a review and correction window
    # Allow the user to make corrections and return the corrected text
    # For simplicity, we'll just return the original text for now
    return ocr_text

def save_corrected_text(corrected_text):
    # Save the corrected text to the corrections folder
    corrected_text_file = os.path.join(corrections_folder, "corrected_text.txt")
    with open(corrected_text_file, "a", encoding="utf-8") as file:
        file.write(corrected_text + "\n")

def ask_permission():
    user_response = input("Do you want to search and download new Punjabi fonts? (yes/no): ").strip().lower()
    return user_response == "yes"

def train_tesseract_with_corpus():
    # Perform the font training here
    # You'll need to use command-line tools to create traineddata files
    # Unfortunately, this cannot be done within this Python script
    pass

def main():
    create_directories()

    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename()

    if not file_path:
        print("No file selected. Exiting.")
        return

    if os.path.isfile(file_path):
        if file_path.endswith(('.gif', '.png', '.jpg', '.jpeg', '.jpg')):
            process_user_images(file_path)
        elif file_path.endswith('.pdf'):
            process_user_pdfs(file_path)

        ocr_text = '\n'.join(punjabi_corpus)
        with open('user_ocr_output.txt', 'w', encoding='utf-8') as output_file:
            output_file.write(ocr_text)

    elif os.path.isdir(file_path):
        for filename in os.listdir(file_path):
            file_path = os.path.join(file_path, filename)
            if filename.endswith(('.gif', '.png', '.jpg', '.jpeg', '.jpg')):
                process_user_images(file_path)
            elif filename.endswith('.pdf'):
                process_user_pdfs(file_path)

        ocr_text = '\n'.join(punjabi_corpus)
        with open('user_ocr_output.txt', 'w', encoding='utf-8') as output_file:
            output_file.write(ocr_text)

    train_tesseract_with_corpus()

if __name__ == "__main__":
    main()
