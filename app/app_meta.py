from flask import Flask, redirect, request, send_file
import os
import traceback

from PIL import Image
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
    if 'form_file' in request.files:
        file = request.files['form_file']
        if file.filename != '':
            # Save the uploaded file to the 'files' directory
            file.save(os.path.join("files", os.path.basename(file.filename)))

    return redirect("/")



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
     
    image_html="<h2>"+filename+"</h2>"+ \
       '<img src = "/image/'+filename+'" width="500" height="333">'
    image=Image.open(os.path.join("./files", filename))
    exifdata=image.getexif()

    image_html+='<table border=1 width="500">'

    for tagid in exifdata:
         tagname=TAGS.get(tagid, tagid)
         value= exifdata.get(tagid)
         image_html+='<tr><td>'+tagname+'</td><td>'+str(value)+'</td></tr>'
    image_html+="</table>"
    image_html='<br><a href="/"back</a>'

    return image_html

@app.route('/image/<filename>')
def get_image(filename):
     print('GET /image/'+filename)

     return send_file(os.path.join("./files",filename))
    

if __name__ == '__main__':
    app.run(debug=True)