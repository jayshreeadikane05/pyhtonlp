import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, request, send_file, render_template, jsonify, url_for
from werkzeug.utils import secure_filename
import zipfile
import io
import tempfile
from flask_cors import CORS
from flask_socketio import SocketIO, emit
app = Flask(__name__)
socketio = SocketIO(app)
CORS(app, resources={r"/*": {"origins": "http://192.168.1.236:3000"}})
socketio = SocketIO(app, cors_allowed_origins="http://192.168.1.236:3000")
def read_excel(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()  
    return df

def fetch_webpage(url):
    response = requests.get(url)
    return response.content

def replace_form_content(html_content, new_form_snippet, redirect_url, output_folder, base_url):
    modified_snippet = new_form_snippet.replace('// Add code to deliver asset here', f'window.location.replace("https://{redirect_url}");')
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for tag in soup.find_all(attrs={"data-isembedded": "false"}):
        tag['data-isembedded'] = "true"  
    
    form_subheading_tag = soup.find(id="form-subheading")
    if form_subheading_tag:
        form_subheading_tag.decompose()
    
    form_tag = soup.find('form')

    if form_tag:
        form_tag.clear()
        form_tag.append(BeautifulSoup(modified_snippet, 'html.parser'))
        return str(soup)
    else:
        return None

def generate_folder_name_from_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip('/').split('/')
    
    if len(path_parts) > 1:
        folder_structure = os.path.join(*path_parts[:-1])
        return folder_structure
    else:
        return 'default_folder'  

def generate_filename_from_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip('/').split('/')
    
    if path_parts:
        return path_parts[-1]
    else:
        return 'default_filename.html'  

def process_excel(file_path, output_zip_path):
    df = read_excel(file_path)
    total_rows = df.shape[0]
    with zipfile.ZipFile(output_zip_path, 'w') as zip_file:
        for index, row in df.iterrows():
            url = row['URL']
            new_form_snippet = row['Form Snippet']
            redirect_url = row['Redirect URL']
            html_content = fetch_webpage(url)
            progress = int(((index + 1) / total_rows) * 100)
            socketio.emit('progress_update', {'progress': progress})
            folder_structure = generate_folder_name_from_url(url)
            images_folder = os.path.join(folder_structure, 'images') 
            
            os.makedirs(images_folder, exist_ok=True)   
            
            modified_html = replace_form_content(html_content, new_form_snippet, redirect_url, images_folder, url)
            
            if modified_html:
                file_name = generate_filename_from_url(url)
                html_path = os.path.join(folder_structure, f'{file_name}')
                
                zip_file.writestr(html_path, modified_html)  
            else:
                continue

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if file:
        os.makedirs('uploads', exist_ok=True)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join('uploads', filename)
        file.save(file_path)

        # Create a temporary file for the zip output
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip_file:
            output_zip_path = temp_zip_file.name

        process_excel(file_path, output_zip_path)

        # Return a JSON response with the download URL
        download_url = url_for('download_file', filename=os.path.basename(output_zip_path), _external=True)
        return jsonify({"message": "File processed successfully", "download_url": download_url})

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    zip_path = os.path.join(tempfile.gettempdir(), filename)
    
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True, download_name='modified_htmls.zip', mimetype='application/zip')
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("FLASK_RUN_PORT", 5001))  # Get the port from environment variable
    app.run(host="0.0.0.0", port=port)  # Run the app on the specified port
    socketio.run(app, host="0.0.0.0", port=port, debug=True)