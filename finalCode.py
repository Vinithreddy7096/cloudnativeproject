from flask import Flask, redirect, request, send_file, render_template, flash, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from google.cloud import storage
import os
import logging
import google.generativeai as genai
import json
import requests
import io  # Added for downloading files from URLs

app = Flask(__name__)
app.config['template_folder'] = '/home/vinithreddy_nagelly1999/cloudnativeproject/cc_project2/templates'
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-secret-key')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'signin'

# Simulating a user database with their uploaded files
users = {}  # Format: {email: {'id': email, 'email': email, 'password': password, 'files': []}}
file_info = []

class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user['id'] == user_id:
            return User(user['id'], user['email'])
    return None

# Initialize Google Cloud Storage client
storage_client = storage.Client()
bucket_name = 'cloudnative-434921.appspot.com'
bucket = storage_client.bucket(bucket_name)

# Set the Google API key
os.environ['GEMINI_API_KEY'] = 'AIzaSyCG4o9x9cm014I6bhCLjcubrtyOW0OdYwo'
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError("API Key not found. Make sure to set the GEMINI_API_KEY environment variable.")

# Configure the Google Generative AI SDK
genai.configure(api_key=api_key)

# Initialize the description_data_list as a dictionary
description_data_list = {}

# Function to upload a file to Gemini
def upload_to_gemini(file_path, mime_type=None):
    """Uploads the given file to Gemini."""
    try:
        file = genai.upload_file(file_path, mime_type=mime_type)
        print(f"Uploaded file '{file.display_name}' as: {file.uri}")
        return file
    except Exception as e:
        print(f"Error uploading file to Gemini: {e}")
        return None

# Function to generate image description and title using Gemini
def generate_image_description(uploaded_file):
    """Generate title and description using the Gemini API."""
    try:
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
        )

        chat_session = model.start_chat()
        image_data = upload_to_gemini(uploaded_file, mime_type="image/jpeg")

        response = chat_session.send_message({
            "parts": [
                image_data,
                "Please provide a title and description for the image."
            ]
        })

        if hasattr(response, 'text'):
            return response.text
        else:
            return None

    except Exception as e:
        print(f"Error generating description: {e}")
        return None

@app.route('/')
@login_required
def index():
    # Get the files uploaded by the current user
    user_files = users[current_user.email].get('files', [])
    return render_template('index.html', files=user_files, description_data_list=description_data_list)

@app.route("/upload", methods=['POST'])
@login_required
def upload():
    try:
        file = request.files.get('form_file')
        if file:
            temp_file_path = f"/tmp/{file.filename}"
            file.save(temp_file_path)  # Save to a temporary path

            # Upload directly to Google Cloud Storage
            blob = bucket.blob(file.filename)
            blob.upload_from_filename(temp_file_path)
            blob.make_private()

            # Store the file under the current user
            users[current_user.email]['files'].append(file.filename)

            # Upload the file to Gemini
            uploaded_file = temp_file_path
            description_data = generate_image_description(uploaded_file)
            if description_data:
                description_data_list[file.filename] = description_data
                description_filename = f"{file.filename}_description.txt"
                save_description_to_gcs(description_data, description_filename)
            else:
                print("No description data generated.")
        else:
            print("No file uploaded")
    except Exception as e:
        print(f"Error: {e}")

    return redirect('/')

def save_description_to_gcs(description_data, filename):
    description_string = json.dumps(description_data, indent=4)
    blob = bucket.blob(filename)
    blob.upload_from_string(description_string, content_type='text/plain')
    blob.make_public()  # Optional: make the file public if needed
    print(f"Description saved as: {filename}")

@app.route('/files')
@login_required
def list_files():
    # List the files for the current user only
    user_files = users[current_user.email].get('files', [])
    return user_files

@app.route('/files/<filename>')
@login_required
def get_file(filename):
    # Ensure the current user owns the file
    if filename not in users[current_user.email].get('files', []):
        flash("You don't have access to this file.")
        return redirect('/')

    # Provide a default info_dict as a dictionary
    info_dict = {
        "Filename": filename,
        "File URL": f"/image/{filename}",
    }

    return render_template('file_details.html', filename=filename, info_dict=info_dict)


@app.route('/image/<filename>')
@login_required
def get_image(filename):
    # Ensure the current user owns the file
    if filename not in users[current_user.email].get('files', []):
        flash("You don't have access to this image.")
        return redirect('/')

    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    return send_file(io.BytesIO(image_bytes), mimetype='image/jpeg')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if email in users:
            flash('Email already exists')
        else:
            users[email] = {'id': email, 'email': email, 'password': password, 'files': []}
            flash('Sign-up successful! You can now sign in.')
            return redirect(url_for('signin'))

    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if email in users and users[email]['password'] == password:
            user = User(users[email]['id'], email)
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials')

    return render_template('signin.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/signin')

@app.route('/delete/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    # Ensure the current user owns the file
    if filename not in users[current_user.email].get('files', []):
        flash("You don't have permission to delete this file.")
        return redirect('/')

    try:
        blob = bucket.blob(filename)
        blob.delete()  # Delete the blob from the bucket
        users[current_user.email]['files'].remove(filename)  # Remove from user file list
        flash(f'File {filename} has been deleted.')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}')

    return redirect('/')

if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
