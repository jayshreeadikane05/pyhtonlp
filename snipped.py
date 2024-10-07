import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, request, send_file

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'  # Set your upload folder here
app.config['DOWNLOAD_FOLDER'] = 'downloads'  # Set your download folder here

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Function to read the uploaded Excel file and clean up column names
def read_excel(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()  # Strip any extra spaces from column names
    return df

def fetch_webpage(url):
    response = requests.get(url)
    return response.content

# Function to download an image from a URL and save it in the specified folder
def download_image(image_url, output_folder):
    response = requests.get(image_url)
    image_name = os.path.basename(urlparse(image_url).path)
    image_path = os.path.join(output_folder, image_name)

    with open(image_path, 'wb') as file:
        file.write(response.content)

    return image_name

# Function to replace the image paths in the HTML content and download the images locally
def replace_image_paths(soup, output_folder, base_url):
    for img_tag in soup.find_all('img'):
        img_url = img_tag['src']  # Get the image URL from the src attribute
        full_img_url = urljoin(base_url, img_url)  # Build the full URL
        image_name = download_image(full_img_url, output_folder)  # Download the image
        img_tag['src'] = os.path.join('images', image_name)  # Update the src attribute to point to the local image

# Function to replace the content inside the <form> tag with a new form snippet
def replace_form_content(html_content, new_form_snippet, redirect_url, output_folder, base_url):
    modified_snippet = new_form_snippet.replace('// Add code to deliver asset here', f'window.location.replace("https://{redirect_url}");')
    soup = BeautifulSoup(html_content, 'html.parser')  # Parse the HTML content
    
    # Remove the element with id="form-subheading"
    form_subheading_tag = soup.find(id="form-subheading")
    if form_subheading_tag:
        form_subheading_tag.decompose()  # Remove the tag entirely from the HTML
    
    replace_image_paths(soup, output_folder, base_url)  # Replace image paths and download images
    form_tag = soup.find('form')  # Find the <form> tag

    if form_tag:
        form_tag.clear()  # Remove all content inside the <form> tag
        form_tag.append(BeautifulSoup(modified_snippet, 'html.parser'))  # Add the new form snippet inside the <form> tag
        return str(soup)  # Return the modified HTML as a string
    else:
        return None

# Function to generate a folder name from the URL based on the first part after the domain
def generate_folder_name_from_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip('/').split('/')
    if path_parts:
        return path_parts[0]  # Return the first part after the domain as the folder name
    else:
        return 'default_folder'  # Fallback if no valid folder name can be extracted

# Function to generate a filename based on the last three parts of the URL path
def generate_filename_from_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip('/').split('/')
    
    if len(path_parts) >= 3:
        last_three = path_parts[-3:]  # Get the last three parts of the URL path
    else:
        last_three = path_parts
    
    filename = "-".join(last_three)  # Join the parts with "-" to form the filename
    return filename

# Function to save the modified HTML content to a file in the specified folder
def save_modified_html(folder_name, file_name, modified_html):
    os.makedirs(folder_name, exist_ok=True)  # Create the folder if it doesn't exist
    file_path = os.path.join(folder_name, file_name)  # Construct the file path
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(modified_html)

def process_excel(file_path):
    df = read_excel(file_path)  

    for index, row in df.iterrows():
        url = str(row.get('link', ''))
        new_form_snippet = str(row.get('snippets', ''))
        redirect_url = str(row.get('pdflink', '')) 
        
        html_content = fetch_webpage(url)  
        
        folder_name = os.path.join(app.config['DOWNLOAD_FOLDER'], generate_folder_name_from_url(url))
        images_folder = os.path.join(folder_name, 'images')  
        os.makedirs(images_folder, exist_ok=True)  
        
        modified_html = replace_form_content(html_content, new_form_snippet, redirect_url, images_folder, url)  # Replace the form content and update the HTML
        
        if modified_html:
            file_name = generate_filename_from_url(url) + '.html'  
            save_modified_html(folder_name, file_name, modified_html)  # Save the modified HTML to a file inside the new folder
            print(f'Successfully modified and saved HTML for {url} as {file_name} in folder {folder_name}')
        else:
            print(f'No form tag found in {url}')

@app.route('/')
def index():
    return render_template('newindex.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part"
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file"
    
    # Save the uploaded file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Process the uploaded Excel file
    process_excel(file_path)

    return "File processed successfully!"

@app.route('/download/<path:solutionarea>/<path:assetname>/<path:country>/<path:language>/<path:html_filename>', methods=['GET'])
def download_html(solutionarea, assetname, country, language, html_filename):
    download_path = os.path.join(app.config['DOWNLOAD_FOLDER'], solutionarea, assetname, country, language, html_filename)
    return send_file(download_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
