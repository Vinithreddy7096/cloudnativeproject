from flask import Flask, redirect, request, send_file, render_template
from google.cloud import storage
import io
from PIL import Image, ExifTags
import os
import google.generativeai as genai

app = Flask(__name__)

# Initialize the Google Cloud Storage client
storage_client = storage.Client()
bucket_name = 'cloudnative-434921.appspot.com' 
bucket = storage_client.bucket(bucket_name)

GOOGLE_API_KEY = "AIzaSyCG4o9x9cm014I6bhCLjcubrtyOW0OdYwo"


# Configure Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
print(f"GEMINI_API_KEY: {api_key}")  # Debugging line
genai.configure(api_key=api_key)

def upload_to_gemini(image_bytes, mime_type=None):
    """Uploads the given image bytes to Gemini."""
    try:
        print("Attempting to upload image to Gemini.")  # Debugging line
        file = genai.upload_file(io.BytesIO(image_bytes), mime_type=mime_type)
        print(f"Uploaded file '{file.display_name}' as: {file.uri}")
        return file
    except Exception as e:
        print(f"Error uploading to Gemini: {str(e)}")  # Log the error message
        return None

def check_file_existence(bucket_name, filename):
    """Check if the file exists in the specified GCS bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    return blob.exists()

@app.route('/')
def index():
    print("GET /")
    index_html = """
    <!doctype html>
    <html>
    <head>
        <title>File Upload</title>
    </head>
    <body>
        <h1>Upload and View Images</h1>
        <form method="post" enctype="multipart/form-data" action="/upload">
            <div>
                <label for="file">Choose file to upload</label>
                <input type="file" id="file" name="form_file" accept="image/jpeg,image/jpg" />
            </div>
            <div>
                <button type="submit">Submit</button>
            </div>
        </form>
        <h2>Uploaded Files</h2>
        <ul>
    """

    for file in list_files():
        if file.lower().endswith(('.jpg', '.jpeg')):
            index_html += f"""
            <li>
                <a href="/files/{file}">{file}</a><br>
                <img src="/files/{file}" width="200" height="auto">
            </li>
            """

    index_html += """
        </ul>
    </body>
    </html>
    """
    return index_html

@app.route("/upload", methods=['POST'])
def upload():
    try:
        print("POST /upload")
        file = request.files.get('form_file')
        if file:
            # Upload directly to Google Cloud Storage
            blob = bucket.blob(file.filename)
            blob.upload_from_file(file.stream)

            # Optionally, make the file publicly accessible
            blob.make_public()

            print(f"File uploaded: {file.filename}")
        else:
            print("No file uploaded")
    except Exception as e:
        print(f"Error: {e}")

    return redirect('/')

@app.route('/files')
def list_files():
    print("GET /files")
    blobs = storage_client.list_blobs(bucket_name)
    jpegs = [blob.name for blob in blobs if blob.name.endswith(".jpeg") or blob.name.endswith(".jpg")]
    print(jpegs)
    return jpegs

@app.route('/files/<filename>')
def get_file(filename):
    print("GET /files/" + filename)
    if not check_file_existence(bucket_name, filename):
        return f"File {filename} does not exist.", 404

    # Download the file from GCS directly into memory
    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    # Initialize an empty HTML string
    image_html = "<h2>" + filename + "</h2>"
    image_html += '<img src="/image/' + filename + '" width="500" height="333">'

    # Open the image and retrieve its EXIF metadata
    image = Image.open(io.BytesIO(image_bytes))
    exifdata = image._getexif()

    # Extract other basic metadata
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

    # Create an HTML table for metadata
    image_html += '<table border="1" width="500">'
    for label, value in info_dict.items():
        image_html += f'<tr><td>{label}</td><td>{value}</td></tr>'
        print(f"{label:25}: {value}")

    if exifdata:
        for tag_id, value in exifdata.items():
            tag_name = ExifTags.TAGS.get(tag_id, tag_id)
            image_html += f'<tr><td>{tag_name}</td><td>{value}</td></tr>'
    else:
        image_html += '<tr><td>EXIF data not available</td></tr>'

    # Close the table
    image_html += "</table>"
    image_html += '<br><a href="/">Back</a>'

    return image_html

@app.route('/image/<filename>')
def get_image(filename):
    print('GET /image/' + filename)
    if not check_file_existence(bucket_name, filename):
        return f"File {filename} does not exist.", 404

    # Download the file from GCS directly into memory
    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    # Serve the file directly from memory
    return send_file(io.BytesIO(image_bytes), mimetype='image/jpeg')

@app.route('/generate/<filename>')
def generate_caption_and_description(filename):
    """Generates a caption and description using the Gemini model."""
    if not check_file_existence(bucket_name, filename):
        return f"File {filename} does not exist.", 404

    # Download the file from GCS directly into memory
    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    uploaded_file = upload_to_gemini(image_bytes, mime_type="image/jpeg")
    if uploaded_file is None:
        return "Failed to upload file to Gemini."

    try:
        # Start the chat session and request a caption and description
        chat_session = genai.chat(model="gemini-1.5-flash")  # Ensure the correct model is set
        message = f"Generate a description and caption for the uploaded image: {filename}"
        response = chat_session.send_message(message)

        print(f"Response from Gemini: {response.text}")
        return response.text
    except Exception as e:
        print(f"Error during chat session: {e}")
        return "Error generating caption and description."

@app.route('/signin')
def signin():
    return render_template('signin.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/reset_password')
def reset_password():
    return render_template('reset_password.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
