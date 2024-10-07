from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, flash, send_from_directory
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager # type: ignore
from datetime import datetime
from flask_cors import CORS
import pandas as pd
import os
from lxml import html
import io
import zipfile
import uuid
import re
from flask_socketio import SocketIO, emit

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.secret_key = 'supersecretkey'

socketio = SocketIO(app)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})  # Allow your client origin
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3000")  # Allow your client origin
def slugify(value):
    if not isinstance(value, str):
        value = str(value) 
    value = value.lower()
    value = re.sub(r'\s+', '-', value) 
    value = re.sub(r'[^\w\-]', '', value) 
    value = re.sub(r'\-+', '-', value) 
    value = value.strip('-') 
    return value

def countryslugify(value):
    if not isinstance(value, str):
        value = str(value) 
    value = re.sub(r'\s+', '-', value)  
    value = re.sub(r'[^\w\-]', '', value) 
    value = re.sub(r'\-+', '-', value) 
    value = value.strip('-') 
    return value

def should_skip_element(tag):
 
    if tag.has_attr('class'):
        classes = tag['class']
        if 'hidden' in classes or 'invisible' in classes:
            return True
    if tag.has_attr('style'):
        style = tag['style']
        if 'display: none' in style:
            return True
    return False

def remove_display_none_elements(soup):
 
    for element in soup.find_all(style=re.compile(r'display:\s*none', re.I)):
        element.decompose()

def is_visible(tag):
    if tag.has_attr('class'):
        classes = tag['class']
        if 'hidden' in classes or 'invisible' in classes:
            return False
    if tag.has_attr('style'):
        style = tag['style']
        if 'display: none' in style or 'visibility: hidden' in style:
            return False
    return True


@app.route('/')
def index():
    return render_template('newindex.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        enter_html_name = request.form.get('namehtml', '')
        if 'file' not in request.files:
            flash('No file part')
            return redirect(url_for('index'))
        file = request.files['file']
        
        
        if file.filename == '':
            flash('No file selected for uploading')
            return redirect(url_for('index'))

        if file and file.filename.endswith('.xlsx'):
            filename = str(uuid.uuid4()) + '.xlsx' 
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
          
            return redirect(url_for('scrape', filename=filename, namehtml=enter_html_name))

        else:

            flash('Invalid file type. Please upload an Excel file.')

            return redirect(url_for('index'))

    except Exception as e:
        print(f"An error occurred: {e}")
        flash(f"An error occurred: {e}")
        return redirect(url_for('index'))

@app.route('/scrape/<filename>', methods=['GET'])
def scrape(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = pd.read_excel(file_path)
        zip_filename = f'{filename.split(".")[0]}.zip'
        zip_filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], zip_filename)

        # Start the zip file creation
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for index, row in df.iterrows():
                url = str(row.get('link', ''))
                country = countryslugify(row.get('country', ''))
                language = str(row.get('language', ''))
                solutionarea = str(row.get('solution', ''))
                assetname = slugify(row.get('assetname', ''))
                snipped = str(row.get('snippets', ''))
                pdf_link = str(row.get('pdflink', ''))
                enter_html_name = request.args.get('namehtml', '')

                # Attempt to retrieve the page
                response = requests.get(url)
                if response.status_code != 200:
                    print(f"Failed to retrieve the URL: {url}. Status code: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Find the form tag
                form_tag = soup.find('form')
                if form_tag:
                    # Clear the contents of the form tag without altering original content
                    for element in form_tag.find_all(True):
                        element.decompose()

                    # Update the form with the new snippet
                    snippet_tag = BeautifulSoup(snipped, 'html.parser')
                    updated_snippet = snippet_tag.prettify().replace(
                        "// Add code to deliver asset here",
                        f'window.location.replace("{pdf_link}");'
                    )
                    form_tag.append(BeautifulSoup(updated_snippet, 'html.parser'))

                    # Update the data-isembedded attribute only if needed
                    div_tag = soup.find('div', {'class': 'solutions-area', 'data-isembedded': 'false'})
                    if div_tag:
                        div_tag['data-isembedded'] = 'true'
                else:
                    print(f"No form tag found for URL: {url}")
                    continue

                # Save the updated HTML content
                updated_html_content = str(soup)

                # Determine the filename based on form type
                if row.get('formtype', '') == 'standard':
                    html_filename = f'{enter_html_name}.html'
                elif row.get('formtype', '') == 'embedded-forms':
                    html_filename = f'embedded-forms-{enter_html_name}.html'
                else:
                    print(f"Invalid form type for URL: {url}. Skipping.")
                    continue

                # Create directory structure for the download file
                download_html_file = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, html_filename)
                os.makedirs(os.path.dirname(download_html_file), exist_ok=True)

                # Write the HTML content to the file
                try:
                    with open(download_html_file, 'w', encoding='utf-8') as file:
                        file.write(updated_html_content)
                        print(f"Successfully created HTML file: {download_html_file}")  # Debugging line
                except Exception as e:
                    print(f"Error writing file {download_html_file}: {e}")

                # Add the file to the zip file
                zipf.write(download_html_file, os.path.relpath(download_html_file, app.config['DOWNLOAD_FOLDER']))

        flash('Scraping and zip creation completed successfully')
        return redirect(url_for('download_zip', filename=zip_filename))

    except Exception as e:
        print(f"An error occurred: {e}")
        flash(f"An error occurred: {e}")
        return redirect(url_for('index'))



@app.route('/download_zip/<filename>')
def download_zip(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)


def download_pdf(url, path):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"PDF downloaded and saved to {path}")
            
        else:
            print(f"Failed to download PDF from {url}. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred while downloading the pdf from {url}: {e}")
def download_image(url, path):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            if not os.path.splitext(path)[1]:
                path += '.png'
            
            with open(path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"Image downloaded and saved to {path}")
        else:
            print(f"Failed to download image from {url}. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred while downloading the image from {url}: {e}")

def get_image_extension(url):
    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'image/jpeg' in content_type:
                return '.jpg'
            elif 'image/png' in content_type:
                return '.png'
            elif 'image/gif' in content_type:
                return '.gif'
            elif 'image/bmp' in content_type:
                return '.bmp'
            elif 'image/webp' in content_type:
                return '.webp'
        return None
    except Exception as e:
        print(f"An error occurred while determining the image type: {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True)
    socketio.run(app, debug=True)
