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
    value = value.lower()
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

        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for index, row in df.iterrows():
                url = row['link']
                country = slugify(row['country'])
                language = row['language']
                solutionarea = row['solution']
                assetname = slugify(row['assetname'])
                scrp_style = row.get('scrp_style', '')
                pdflink = row.get('pdflinks', '')

                try:
                    existing_html_file = 'mainfilewebinar.html'
                    with open(existing_html_file, 'r', encoding='utf-8') as file:
                        existing_html_content = file.read()

                    response = requests.get(url)
                    if response.status_code != 200:
                        print(f"Failed to retrieve the URL. Status code: {response.status_code}")
                        continue

                    soup = BeautifulSoup(response.text, 'html.parser')
                    remove_display_none_elements(soup)

                    page_title_div = soup.find('div', {'id': 'pageTitle'})
                    page_title = page_title_div.get_text(strip=True) if page_title_div else "No Title Found"

                    halfbanner_img = soup.find('div', {'class': 'halfbannerwrapper'})
                    if halfbanner_img and not should_skip_element(halfbanner_img):
                        halfbanner_img = halfbanner_img.find('img')
                        halfbanner_url = halfbanner_img['src'] if halfbanner_img else None
                    else:
                        halfbanner_url = None

                    fullbanner_img = soup.find('div', {'class': 'fullbanner'})
                    if fullbanner_img and not should_skip_element(fullbanner_img):
                        fullbanner_img = fullbanner_img.find('img')
                        fullbanner_url = fullbanner_img['src'] if fullbanner_img else None
                    else:
                        fullbanner_url = None

                    # carousel_section = soup.find('div', {'class': 'carouselSpeakerSection'})
                    # if carousel_section and not should_skip_element(carousel_section):
                    #     carousel_images = carousel_section.find_all('img')
                    #     for i, img in enumerate(carousel_images):
                    #         img_url = img['src']
                    #         image_folder = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, 'images')
                    #         os.makedirs(image_folder, exist_ok=True)
                    #         image_path = os.path.join(image_folder, f'{i + 1}.png')  # Assigning random names like 1.png, 2.png, ...
                    #         download_image(img_url, image_path)

                    #         # Replace img src in HTML with relative path
                    #         img['src'] = f'images/{i + 1}.png'

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

                        if main_section_str:
                            main_fragment = html.fragment_fromstring(main_section_str, parser)
                            parent.append(main_fragment)

                        # if carousel_section:
                        #     carousel_fragment = html.fragment_fromstring(str(carousel_section), parser)
                        #     parent.append(carousel_fragment)
                    else:
                        print(f"Target section 'mainBodyCopy3' not found in the existing HTML for URL: {url}")
                        continue

                    image_folder = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, 'images')
                    os.makedirs(image_folder, exist_ok=True)

                    if halfbanner_url:
                        halfbanner_filename = os.path.join(image_folder, os.path.basename(halfbanner_url))
                        download_image(halfbanner_url, halfbanner_filename)
                        halfbanner_element = root.xpath('//img[@id="thumbnail-img"]')
                        if halfbanner_element:
                           
                            halfbanner_element[0].attrib['src'] = f'images/{os.path.basename(halfbanner_filename)}'

                    if fullbanner_url:
                        fullbanner_filename = os.path.join(image_folder, os.path.basename(fullbanner_url))
                        download_image(fullbanner_url, fullbanner_filename)
                        jumbotron_div = root.xpath('//div[@class="jumbotron"]')
                        if jumbotron_div:
                         
                            jumbotron_div[0].attrib['style'] = f"background: url('images/{os.path.basename(fullbanner_filename)}') no-repeat; background-size: cover; background-color: #0078D7;"

                    if scrp_style:
                        style_tag = html.Element('style')
                        style_tag.text = scrp_style
                        head_tag = root.find('.//head')
                        if head_tag is not None:
                            head_tag.append(style_tag)


                    input_pdf = root.xpath('//input[@id="pdffile"]')
                    if input_pdf:
                        input_pdf[0].attrib['value'] = pdflink
                        print(f'Success: Updated input value to {pdflink}')
                    else:
                        print("Error: Could not find <input> element with id='pdflinks' in the HTML.")


                    updated_html_content = html.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')

                    html_filename = f'{len(html_files) + 1}.html'
                    download_html_file = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, html_filename)
                    with open(download_html_file, 'w', encoding='utf-8') as file:
                        file.write(updated_html_content)

                    html_files.append(download_html_file)

                    # Add images folder to the ZIP
                    if os.path.exists(image_folder):
                        for root_dir, _, files in os.walk(image_folder):
                            for file in files:
                                file_path = os.path.join(root_dir, file)
                                zipf.write(file_path, os.path.relpath(file_path, app.config['DOWNLOAD_FOLDER']))

                except Exception as e:
                    print(f"An error occurred while scraping {url}: {e}")
                    continue

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


if __name__ == '__main__':
    app.run(debug=True)
