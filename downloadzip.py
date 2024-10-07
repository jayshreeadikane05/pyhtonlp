from flask import Flask, request, send_file, render_template, redirect, url_for, flash, send_from_directory
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from lxml import html
import io
import zipfile
import uuid
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.secret_key = 'supersecretkey'

def slugify(value):
    if not isinstance(value, str):
        value = str(value)  # Convert non-string to string
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

@app.route('/')
def index():
    return render_template('newindex.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
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
            
            return redirect(url_for('scrape', filename=filename))

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
        html_files = []
        zip_filename = f'{filename.split(".")[0]}.zip'
        zip_filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], zip_filename)
        folder_counters = {}
        updated_links = []

        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for index, row in df.iterrows():
                url = str(row.get('link', ''))
                country = countryslugify(row.get('country', ''))
                language = str(row.get('language', ''))
                solutionarea = str(row.get('solution', ''))
                assetname = slugify(row.get('assetname', ''))
                scrp_style = str(row.get('scrp_style', ''))
                pdflink = str(row.get('pdflinks', ''))
                formtype = slugify(row.get('formtype', ''))
                contenttype = str(row.get('contenttype', ''))
                folder_key = f"{solutionarea}/{assetname}/{country}/{language}"

                if folder_key not in folder_counters:
                    folder_counters[folder_key] = {
                        'standard_counter': 1,
                        'embedded_forms_counter': 1,
                        'pdf_counter': 1
                    }

                # Generate unique HTML filename based on formtype
                if formtype == 'standard':
                    html_filename = f'Q4-1-2024-{folder_counters[folder_key]["standard_counter"]}.html'
                    folder_counters[folder_key]['standard_counter'] += 1
                elif formtype == 'embedded-forms':
                    html_filename = f'embedded-forms-Q4-1-2024-{folder_counters[folder_key]["embedded_forms_counter"]}.html'
                    folder_counters[folder_key]['embedded_forms_counter'] += 1
                else:
                    updated_links.append(None)
                    continue

                updated_link = f"https://ittech-news.com/{assetname}/{country}/{language}/{html_filename}"
                updated_links.append(updated_link)

                try:
                    existing_html_file = 'mainfile.html'
                    with open(existing_html_file, 'r', encoding='utf-8') as file:
                        existing_html_content = file.read()

                    response = requests.get(url)
                    if response.status_code != 200:
                        print(f"Failed to retrieve the URL: {url}. Status code: {response.status_code}")
                        updated_links[-1] = None
                        continue

                    soup = BeautifulSoup(response.text, 'html.parser')
                    remove_display_none_elements(soup)

                    page_title_div = soup.find('div', {'id': 'pageTitle'})
                    page_title = page_title_div.get_text(strip=True) if page_title_div else "No Title Found"

                    halfbanner_img = soup.find('div', {'class': 'halfbannerwrapper'})
                    halfbanner_url = halfbanner_img.find('img')['src'] if halfbanner_img else None

                    fullbanner_img = soup.find('div', {'class': 'fullbanner'})
                    fullbanner_url = fullbanner_img.find('img')['src'] if fullbanner_img else None

                    main_section = soup.find('section', {'id': 'mainBodyCopy'})
                    main_section_str = str(main_section) if main_section and not should_skip_element(main_section) else ""

                    parser = html.HTMLParser(encoding='utf-8')
                    tree = html.parse(io.StringIO(existing_html_content), parser)
                    root = tree.getroot()

                    title_tag = root.find('.//title')
                    if title_tag is not None:
                        title_tag.text = page_title
                    else:
                        head_tag = root.find('.//head')
                        if head_tag is not None:
                            head_tag.append(html.Element('title', text=page_title))

                    target_section = root.xpath('//*[@id="mainBodyCopy3"]')
                    if target_section:
                        parent = target_section[0].getparent()
                        parent.remove(target_section[0])
                        parent.append(html.fragment_fromstring(main_section_str))
                    else:
                        print(f"Target section 'mainBodyCopy3' not found in the existing HTML for URL: {url}")
                        continue

                    image_folder = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, 'images')
                    os.makedirs(image_folder, exist_ok=True)

                    if halfbanner_url:
                        image_extension = get_image_extension(halfbanner_url) or '.png'
                        halfbanner_filename = os.path.join(image_folder, os.path.basename(halfbanner_url))
                        download_image(halfbanner_url, halfbanner_filename)
                        halfbanner_element = root.xpath('//img[@id="thumbnail-img"]')
                        if halfbanner_element:
                            halfbanner_element[0].attrib['src'] = f'images/{os.path.basename(halfbanner_filename)}{image_extension}'
                        else:
                            halfbanner_url = None
                    if fullbanner_url:
                        image_extension = get_image_extension(fullbanner_url) or '.png'
                        fullbanner_filename = os.path.join(image_folder, os.path.basename(fullbanner_url))
                        download_image(fullbanner_url, fullbanner_filename)
                        jumbotron_div = root.xpath('//div[@class="jumbotron"]')
                        if jumbotron_div:
                            jumbotron_div[0].attrib['style'] = f"background: url('images/{os.path.basename(fullbanner_filename)}{image_extension}') no-repeat; background-size: cover; background-color: #0078D7;"
                        else:
                            fullbanner_url = None

                    if scrp_style:
                        style_tag = html.Element('style')
                        style_tag.text = scrp_style
                        head_tag = root.find('.//head')
                        if head_tag is not None:
                            head_tag.append(style_tag)

                    pdf_folder = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, 'pdf')
                    os.makedirs(pdf_folder, exist_ok=True)

                    if pdflink:
                        pdf_filename = f'{folder_counters[folder_key]["pdf_counter"]}.pdf'
                        folder_counters[folder_key]['pdf_counter'] += 1
                        pdf_path = os.path.join(pdf_folder, pdf_filename)
                        download_pdf(pdflink, pdf_path)

                        input_pdf = root.xpath('//input[@id="pdffile"]')
                        if input_pdf:
                            input_pdf[0].attrib['value'] = f'pdf/{pdf_filename}'
                            print(f'Success: Updated input value to pdf/{pdf_filename}')
                        else:
                            print("Error: Could not find <input> element with id='pdffile' in the HTML.")

                        zipf.write(pdf_path, os.path.relpath(pdf_path, app.config['DOWNLOAD_FOLDER']))

                    updated_html_content = html.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')

                    download_html_file = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, html_filename)
                    with open(download_html_file, 'w', encoding='utf-8') as file:
                        file.write(updated_html_content)

                    html_files.append(download_html_file)

                    if os.path.exists(image_folder):
                        for root_dir, _, files in os.walk(image_folder):
                            for file in files:
                                file_path = os.path.join(root_dir, file)
                                zipf.write(file_path, os.path.relpath(file_path, app.config['DOWNLOAD_FOLDER']))

                except Exception as e:
                    print(f"An error occurred while scraping {url}: {e}")
                    updated_links[-1] = None
                    continue

            # Debug prints
            print(f"DataFrame rows: {len(df)}")
            print(f"Updated links length: {len(updated_links)}")

            if len(updated_links) == len(df):
                df['updatedlink'] = updated_links
            else:
                print("Error: The length of 'updated_links' does not match the number of rows in the DataFrame.")
                flash('An error occurred: Length mismatch in updated links.')
                return redirect(url_for('index'))

            modified_excel_path = os.path.join(app.config['DOWNLOAD_FOLDER'], f'{filename.split(".")[0]}_updated.xlsx')
            df.to_excel(modified_excel_path, index=False)

            zipf.write(modified_excel_path, os.path.relpath(modified_excel_path, app.config['DOWNLOAD_FOLDER']))

            # After processing all URLs, add all HTML files to the zip
            for html_file in html_files:
                zipf.write(html_file, os.path.relpath(html_file, app.config['DOWNLOAD_FOLDER']))

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
            # Add other image types if necessary
        return None
    except Exception as e:
        print(f"An error occurred while determining the image type: {e}")
        return None


if __name__ == '__main__':
    app.run(debug=True)
