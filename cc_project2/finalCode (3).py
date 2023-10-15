from flask import Flask, redirect, request, send_file
import os
import traceback

from PIL import Image, ExifTags
from PIL.ExifTags import TAGS

app=Flask(__name__)

@app.route('/')
def index():
    print("GET /")

    index_html = """
    <form method="post" enctype="multipart/form-data" action="/upload" method="post">
      <div>
        <label for="file">Choose file to upload</label>
        <input type="file" id="file" name="form_file" accept="image/jpeg" />
      </div>
      <div>
        <button>Submit</button> 
      </div>
      
    </form>
    """

    for file in list_files():
        # Use string formatting to construct the list items
        index_html += "<li><a href=\"/files/" + file + "\">" + file + "</a></li>\n"
    
    return index_html

@app.route("/upload", methods=['POST'])
def upload():
    try:
        print("POST /upload")
        file=request.files['form_file']
        file.save(os.path.join("files", os.path.basename(file.filename)))
    except:
        traceback.print_exc()

    return redirect('/')

@app.route('/files')
def list_files():
    print("GET /files")

    files = os.listdir("./files")
    jpegs = []
    print(files)
    for file in files:
        print(file)
        print(file.endswith(".jpeg"))
        if file.endswith(".jpeg"):
            jpegs.append(file)
        
    print(jpegs)
    return jpegs

@app.route('/files/<filename>')
def get_file(filename):
     print("GET /files/"+filename)
     
     
    # Initialize an empty HTML string
     image_html = "<h2>" +filename+ "</h2>"

    # Insert the image tag
     image_html += '<img src="/image/' + filename + '" width="500" height="333">'

    # Open the image and retrieve its EXIF metadata
     image = Image.open(os.path.join("./files", filename))
     exifdata = image._getexif()
     # extract other basic metadata
     info_dict = {
    "Filename": image.filename,
      "Image Size": image.size,
      "Image Height": image.height,
      "Image Width": image.width,
      "Image Format": image.format,
      "Image Mode": image.mode,
      "Image is Animated": getattr(image, "is_animated", False),
      "Frames in Image": getattr(image, "n_frames", 1)
}
     image_html += '<table border="1" width="500">'

     for label,value in info_dict.items():
      image_html += '<tr><td>' + label + '</td><td>' + str(value) + '</td></tr>'
      print(f"{label:25}: {value}")
    # Create an HTML table

    # Iterate through EXIF tags and display them in the table
     if exifdata is not None:
      for tagid, value in exifdata.items():
        tagname = ExifTags.TAGS.get(tagid, tagid)
        image_html += '<tr><td>' + tagname + '</td><td>' + str(value) + '</td></tr>'
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
     print('GET /image/'+filename)

     return send_file(os.path.join("./files",filename))
    
if  __name__ == "_main_":
  app.run(debug=True)