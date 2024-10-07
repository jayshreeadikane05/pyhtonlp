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

        for index, row in df.iterrows():
            url = row['link']
            country = row['country']
            language = row['language']
            solutionarea = row['solution']
            assetname = slugify(row['assetname'])
            scrp_style = row.get('scrp_style', '') 

            try:
                existing_html_file = 'mainfile.html'  
                with open(existing_html_file, 'r', encoding='utf-8') as file:
                    existing_html_content = file.read()

                response = requests.get(url)
                if response.status_code != 200:
                    print(f"Failed to retrieve the URL. Status code: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Remove elements with display: none using BeautifulSoup
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

                # banner_section = soup.find('div', {'class': 'bannerSectionCarousel'})
                # banner_section_str = str(banner_section) if banner_section and not should_skip_element(banner_section) else ""

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
                    # if banner_section and banner_section_str:
                    #     parent.append(html.fragment_fromstring(banner_section_str))
                else:
                    print(f"Target section 'mainBodyCopy3' not found in the existing HTML for URL: {url}")
                    continue

                halfbanner_element = root.xpath('//img[@id="thumbnail-img"]')
                if halfbanner_element and halfbanner_url:
                    halfbanner_element[0].attrib['src'] = halfbanner_url

                jumbotron_div = root.xpath('//div[@class="jumbotron"]')
                if jumbotron_div and fullbanner_url:
                    jumbotron_div[0].attrib['style'] = f"background: url('{fullbanner_url}') no-repeat; background-size: cover; background-color: #0078D7;"

                if scrp_style:
                    style_tag = html.Element('style')
                    style_tag.text = scrp_style
                    head_tag = root.find('.//head')
                    if head_tag is not None:
                        head_tag.append(style_tag)

                updated_html_content = html.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')

                download_folder = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language)
                os.makedirs(download_folder, exist_ok=True)

                download_html_file = os.path.join(download_folder, f'{uuid.uuid4()}.html')
                with open(download_html_file, 'w', encoding='utf-8') as file:
                    file.write(updated_html_content)

                html_files.append(download_html_file)

            except Exception as e:
                print(f"An error occurred while scraping {url}: {e}")
                continue

        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
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

if __name__ == '__main__':
    app.run(debug=True)
