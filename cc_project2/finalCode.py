from flask import Flask, redirect, request, send_file, render_template
from google.cloud import storage
import io
from PIL import Image, ExifTags
import os
app = Flask(__name__)

# Initialize the Google Cloud Storage client
storage_client = storage.Client()
bucket_name = 'cloudnative-434921.appspot.com'  # Your bucket name
bucket = storage_client.bucket(bucket_name)

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
        # Ensure image files are correctly recognized
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
        traceback.print_exc()

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

    # Download the file from GCS directly into memory
    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    # Initialize an empty HTML string
    image_html = "<h2>" + filename + "</h2>"

    # Insert the image tag
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

    # Add a "Back" link to return to the root
    image_html += '<br><a href="/">Back</a>'

    # Return the generated HTML
    return image_html


@app.route('/image/<filename>')
def get_image(filename):
    print('GET /image/' + filename)

    # Download the file from GCS directly into memory
    blob = bucket.blob(filename)
    image_bytes = blob.download_as_bytes()

    # Serve the file directly from memory
    return send_file(io.BytesIO(image_bytes), mimetype='image/jpeg')


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
