import os
from flask import Flask, request, jsonify, send_file, render_template
import pandas as pd
from werkzeug.utils import secure_filename
from flask_cors import CORS

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
COLLATED_FILE = 'collated_data.xlsx'

# Allow your React frontend origin
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Create the uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Route to render the index.html page (optional)
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle file uploads and collate them
@app.route('/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files')

    if not files:
        return jsonify({'message': 'No files uploaded'}), 400

    df_list = []
    required_columns = [
        "Asset Title / Ad Name", 
        "Vereigen Links", 
        "Snippets 8/27", 
        "Ungated PDFs of the localized eBooks/reports (include local links for all markets)"
    ]

    # Process each uploaded file
    for file in files:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        try:
            # Read the Excel file
            df = pd.read_excel(file_path)

            # Filter columns if they exist
            if all(column in df.columns for column in required_columns):
                df_filtered = df[required_columns]
                df_list.append(df_filtered)
            else:
                print(f"Skipping {filename} - missing required columns.")
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            return jsonify({'message': f"Error processing {filename}: {str(e)}"}), 500

    # Check if any dataframes were added
    if df_list:
        # Concatenate all dataframes
        collated_df = pd.concat(df_list, ignore_index=True)

        # Save the collated dataframe to an Excel file
        collated_file_path = os.path.join(UPLOAD_FOLDER, COLLATED_FILE)
        collated_df.to_excel(collated_file_path, index=False)

        # Return the URL for downloading the file
        return jsonify({'file_url': f'http://localhost:5000/download/{COLLATED_FILE}'})
    else:
        return jsonify({'message': 'No files processed'}), 400

# Route to serve the collated file
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        return jsonify({'message': 'File not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get("FLASK_RUN_PORT", 5002))  # Get the port from environment variable
    app.run(host="0.0.0.0", port=port)
