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
import logging
from flask_socketio import SocketIO, emit

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.secret_key = 'supersecretkey'
logging.basicConfig(filename='app.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')
socketio = SocketIO(app)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Create SocketIO instance
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3000")
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
        selected_quarter = request.form.get('quarter', 'Q1') 
        selected_cycle = request.form.get('cycle', '1')
        selected_solution = request.form.get('datasolution', '') #this by dfault we need
        enter_html_name = request.form.get('namehtml', '')
        if 'file' not in request.files:
            #flash('No file part')
            #return redirect(url_for('index'))
            return jsonify({"error": "No file part in the request"}), 400
        file = request.files['file']
        
        
        if file.filename == '':
            #flash('No file selected for uploading')
            #return redirect(url_for('index'))
            return jsonify({"error": "No file selected for uploading"}), 400

        if file and file.filename.endswith('.xlsx'):
            filename = str(uuid.uuid4()) + '.xlsx' 
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            return jsonify({
                "message": "File uploaded successfully",
                "filename": filename,
                "quarter": selected_quarter,
                "cycle": selected_cycle,
                "datasolution": selected_solution,
                "namehtml": enter_html_name
            }), 200

            # return redirect(url_for('scrape', filename=filename, quarter=selected_quarter, cycle=selected_cycle, datasolution=selected_solution, namehtml=enter_html_name))

        else:

            #flash('Invalid file type. Please upload an Excel file.')
            return jsonify({"error": "Invalid file type. Please upload an Excel file."}), 400

            #return redirect(url_for('index'))

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        #print(f"An error occurred: {e}")
        #flash(f"An error occurred: {e}")
       # return redirect(url_for('index'))

@app.route('/scrape/<filename>', methods=['GET'])
def scrape(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = pd.read_excel(file_path)
        total_rows = df.shape[0]
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
                is_webinar = 'false'
                if contenttype == 'Webinar':
                    is_webinar = 'true'
                progress = int(((index + 1) / total_rows) * 100)
                socketio.emit('progress_update', {'progress': progress})
                if folder_key not in folder_counters:
                    folder_counters[folder_key] = {
                        'standard_counter': 1,
                        'embedded_forms_counter': 1,
                        'pdf_counter': 1
                       
                    }
                selected_quarter = request.args.get('quarter', 'Q1')  
                selected_cycle = request.args.get('cycle', '1')
                selected_solution = request.args.get('datasolution', '')
                enter_html_name = request.args.get('namehtml', '')
                current_year = datetime.now().year
                # Generate unique HTML filename based on formtype
                if formtype == 'standard':
                    html_filename = f'{enter_html_name}.html'
                    folder_counters[folder_key]['standard_counter'] += 1
                elif formtype == 'embedded-forms':
                    html_filename = f'embedded-forms-{enter_html_name}.html'
                    folder_counters[folder_key]['embedded_forms_counter'] += 1
                else:
                    updated_links.append(None)
                    continue

                

              

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
                    halfbanner_url = halfbanner_img.find('img')['src'] if halfbanner_img else None

                    fullbanner_img = soup.find('div', {'class': 'fullbannerwrapper'})
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
                    
                    updated_jslink = f"https://ittech-news.com/js/{selected_solution}-scripts-{current_year}-{selected_quarter}.js"

                    script_tag = root.xpath('//script[@id="javascriptct"]')

                    if script_tag:
                        script_tag[0].attrib['src'] = updated_jslink
                    else:
                        head_tag = root.find('.//head')
                        
                        if head_tag is not None:
                            new_script_tag = html.Element('script', src=updated_jslink, id="javascriptct", defer=True)
                            head_tag.append(new_script_tag)
                        else:
                            print(f"<head> tag not found for {url}")


                    solutions_area_div = root.find('.//div[@class="solutions-area"]')
                    if solutions_area_div is not None:
                        solutions_area_div.set('data-iswebinar', is_webinar)
                        solutions_area_div.set('data-solutions', selected_solution)
                        
                    else:
                        print("solutions-area div not found")

                    target_section = root.xpath('//*[@id="mainBodyCopy3"]')
                    if target_section:
                        parent = target_section[0].getparent()
                        parent.remove(target_section[0])

                        if main_section_str:
                            main_fragment = html.fragment_fromstring(main_section_str, parser)
                            parent.append(main_fragment)

                        if contenttype == 'Webinar':
                            carousel_section = soup.find('div', {'class': 'carouselSpeakerSection'})
                        
                            if carousel_section and is_visible(carousel_section):
                                carousel_images = carousel_section.find_all('img')
                                for i, img in enumerate(carousel_images):
                                    img_url = img['src']
                                    image_folder = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, 'images')
                                    os.makedirs(image_folder, exist_ok=True)
                                    image_path = os.path.join(image_folder, f'{i + 1}.png')  
                                    download_image(img_url, image_path)

                                    img['src'] = f'images/{i + 1}.png'

                                carousel_fragment = html.fragment_fromstring(str(carousel_section), parser)
                                print(carousel_fragment)
                                parent.append(carousel_fragment)
                    else:
                        print(f"Target section 'mainBodyCopy3' not found in the existing HTML for URL: {url}")
                        continue

                    image_folder = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, 'images')
                    os.makedirs(image_folder, exist_ok=True)

                    if halfbanner_url:
                        image_extension = '.png'
                        halfbanner_filename = os.path.join(image_folder, os.path.basename(halfbanner_url))
                        download_image(halfbanner_url, halfbanner_filename)
                        halfbanner_element = root.xpath('//img[@id="thumbnail-img"]')
                        if halfbanner_element:
                            halfbanner_element[0].attrib['src'] = f'images/{os.path.basename(halfbanner_filename)}{image_extension}'
                        else:
                            halfbanner_url = None


                    if fullbanner_img:
                        img_tag = fullbanner_img.find('img')
                        fullbanner_url = img_tag['src'] if img_tag else None

                        if fullbanner_url:
                            image_extension = '.png'
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
                            if contenttype == 'Webinar':
                                input_pdf[0].attrib['value'] = pdflink
                                print(f'Success: Updated input value to {pdflink} for Webinar')
                            else:
                                input_pdf[0].attrib['value'] = f'pdf/{pdf_filename}'
                                print(f'Success: Updated input value to pdf/{pdf_filename}')

                           
                        zipf.write(pdf_path, os.path.relpath(pdf_path, app.config['DOWNLOAD_FOLDER']))


                    updated_html_content = html.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')

                    download_folder_path = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language)

                    os.makedirs(download_folder_path, exist_ok=True)

                    html_filename = increment_filename_if_exists(html_filename, download_folder_path)

                    download_html_file = os.path.join(download_folder_path, html_filename)
                    updated_link = f"https://ittech-news.com/{assetname}/{country}/{language}/{html_filename}"
                    updated_links.append(updated_link)
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
                    updated_links[-1] = None
                    continue
            
            print(f"DataFrame rows: {len(df)}")
            print(f"Updated links length: {len(updated_links)}") 

            if len(updated_links) == len(df):
                df['updatedlink'] = updated_links
            else:
                print("Error: The length of 'updated_links' does not match the number of rows in the DataFrame.")
                flash('An error occurred: Length mismatch in updated links.') 
                return redirect(url_for('index'))
            modified_excel_filename = f'{filename.split(".")[0]}_updated.xlsx'  # Just the filename
            modified_excel_path = os.path.join(app.config['DOWNLOAD_FOLDER'], modified_excel_filename)
            # modified_excel_path = os.path.join(app.config['DOWNLOAD_FOLDER'], f'{filename.split(".")[0]}_updated.xlsx')
            df.to_excel(modified_excel_path, index=False)

            zipf.write(modified_excel_path, os.path.relpath(modified_excel_path, app.config['DOWNLOAD_FOLDER']))

            for html_file in html_files:
                zipf.write(html_file, os.path.relpath(html_file, app.config['DOWNLOAD_FOLDER']))

        logging.info(f"Scraping completed successfully for file: {filename}")

        return jsonify({"message": "Scraping completed successfully", "zipFilename": zip_filename, "updatedExcelSheet" : url_for('download_file', filename=modified_excel_filename)}), 200
    except Exception as e:
       # print(f"An error occurred: {e}")
        # flash(f"An error occurred: {e}")
       # return redirect(url_for('index'))
        return jsonify({"message": "Scraping failed or zip file not generated."}), 400



@app.route('/download_zip/<filename>')
def download_zip(filename):
    try:
        logging.info(f"Downloading zip file: {filename}")
        return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        logging.error(f"Error in download_zip: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download_log', methods=['GET'])
def download_log():
    log_file_path = 'app.log'  # Path to your log file
    if os.path.exists(log_file_path):
        return send_file(log_file_path, as_attachment=True)
    else:
        return jsonify({"error": "Log file not found."}), 404


@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        # Log download attempt
        logging.info(f"Downloading file: {filename}")
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logging.error(f"Error in download_file: {str(e)}")
        return jsonify({"error": str(e)}), 500

def increment_filename_if_exists(base_filename, folder_path):
    counter = 1
    filename, extension = os.path.splitext(base_filename)
    new_filename = base_filename

    while os.path.exists(os.path.join(folder_path, new_filename)):
        new_filename = f"{filename}-{counter}{extension}"
        counter += 1

    return new_filename

def download_pdf(url, path):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"PDF downloaded and saved to {path}")
            logging.info(f"Downloading file: {path}")
        else:
            logging.error(f"Downloading file: {url}")
            print(f"Failed to download PDF from {url}. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Downloading file: {url}")
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
            logging.info(f"Downloading file: {path}")
            print(f"Image downloaded and saved to {path}")
        else:
            logging.error(f"Downloading file: {url}")
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
    port = int(os.environ.get("FLASK_RUN_PORT", 5000))  
    app.run(host="0.0.0.0", port=port) 
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
