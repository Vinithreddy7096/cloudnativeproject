from flask import Flask, redirect, request, send_file, render_template, flash, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from google.cloud import storage
import io
from PIL import Image, ExifTags
import os
import logging
import google.generativeai as genai

# Flask app setup
app = Flask(__name__, template_folder='/home/vinithreddy_nagelly1999/cloudnativeproject/cc_project2/templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-secret-key')

# Set up logging
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'signin'

# Simulating a user database
users = {}

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

# Set the Google API key (ensure this is secure for production)
os.environ['GEMINI_API_KEY'] = 'AIzaSyCG4o9x9cm014I6bhCLjcubrtyOW0OdYwo'  
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError("API Key not found. Make sure to set the GEMINI_API_KEY environment variable.")

# Configure the Google Generative AI SDK
genai.configure(api_key=api_key)

# Function to upload a file to Gemini
def upload_to_gemini(file_path, mime_type=None):
    """Uploads the given file to Gemini."""
    try:
        file = genai.upload_file(file_path, mime_type=mime_type)
        app.logger.info(f"Uploaded file '{file.display_name}' as: {file.uri}")
        return file
    except Exception as e:
        app.logger.error(f"Error uploading file to Gemini: {e}")
        return None

# Function to generate image description and title using Gemini
def generate_image_description(uploaded_file):
    """Generate title and description using the Gemini API."""
    try:
        # Define model configuration
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }

        # Create the model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
        )

        # Start a chat session with the model
        chat_session = model.start_chat()

        image_data = upload_to_gemini(uploaded_file, mime_type="image/jpeg")
        
        # Send the image data to the model
        response = chat_session.send_message({
            "parts": [
                image_data,
                "Please provide a title and detailed description for this image in JSON format."
            ]
        })

        # If response has text, return it
        if hasattr(response, 'text'):
            return response.text  
        else:
            return None

    except Exception as e:
        app.logger.error(f"Error generating description: {e}")
        return None

@app.route('/')
@login_required
def index():
    blobs = list_files()
    return render_template('index.html', files=blobs, description_data_list=description_data_list)

description_data_list = []

@app.route("/upload", methods=['POST'])
def upload():
    try:
        app.logger.info("POST /upload")
        file = request.files.get('form_file')
        if file:
            temp_file_path = f"/tmp/{file.filename}"
            file.save(temp_file_path)  # Save to a temporary path

            # Upload directly to Google Cloud Storage
            blob = bucket.blob(file.filename)
            blob.upload_from_filename(temp_file_path)
            blob.make_private()
            
            # Upload the file to Gemini
            uploaded_file = temp_file_path
            if uploaded_file:
                # Generate description and title from the Gemini API
                description_data = generate_image_description(uploaded_file)
                if description_data:
                    app.logger.info(f"Description Data: {description_data}")
                    description_data_list.append(description_data)
                else:
                    app.logger.warning("No description data generated.")
            else:
                app.logger.error("Failed to upload the file to Gemini.")
        else:
            app.logger.warning("No file uploaded")
    except Exception as e:
        app.logger.error(f"Error: {e}")

    return redirect('/')

@app.route('/files')
def list_files():
    app.logger.info("GET /files")
    blobs = storage_client.list_blobs(bucket_name)
    jpegs = [blob.name for blob in blobs if blob.name.endswith((".jpeg", ".jpg"))]
    return jpegs

@app.route('/files/<filename>')
def get_file(filename):
    app.logger.info(f"GET /files/{filename}")

    # Download the file from GCS directly into memory
    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    # Open the image and retrieve its EXIF metadata
    image = Image.open(io.BytesIO(image_bytes))
    exifdata = image._getexif()

    # Extract basic metadata
    info_dict = {
        "Filename": filename,
        "Image Size": image.size,
        "Image Height": image.height,
        "Image Width": image.width,
        "Image Format": image.format,
        "Image Mode": image.mode,
        "Image is Animated": getattr(image, "is_animated", False),
        "Frames in Image": getattr(image, "n_frames", 1)
    }

    # Prepare EXIF data if available
    exif_dict = {}
    exifdata = image._getexif()

    # Ensure exifdata is not None before processing
    if exifdata:
        for tag_id, value in exifdata.items():
            tag_name = ExifTags.TAGS.get(tag_id, tag_id)
            exif_dict[tag_name] = value
    else:
        exif_dict = {"Error": "No EXIF data available"}

    return render_template('file_details.html', filename=filename, info_dict=info_dict, exifdata=exif_dict)

@app.route('/image/<filename>')
def get_image(filename):
    app.logger.info(f'GET /image/{filename}')

    # Download the file from GCS directly into memory
    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    # Serve the file directly from memory
    return send_file(io.BytesIO(image_bytes), mimetype='image/jpeg')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if email in users:
            flash('Email already exists')
        else:
            users[email] = {'id': email, 'email': email, 'password': password}
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

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        flash('Password reset functionality is not yet implemented.')
        return redirect(url_for('signin'))
    return render_template('reset_password.html')

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    try:
        app.logger.info(f"DELETE /files/{filename}")
        blob = bucket.blob(filename)
        blob.delete()  # Delete the blob from the bucket
        flash(f'File {filename} has been deleted.')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}')

    return redirect('/')

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"An error occurred: {str(e)}", exc_info=True)
    return "An error occurred", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
