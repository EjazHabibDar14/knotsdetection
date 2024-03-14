from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import subprocess
import base64
import cloudinary
import time
from cloudinary import uploader


app = Flask(__name__)

ENV = 'prod'

if ENV=='dev':
    app.debug=True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost/Knots_Detection'
else:
    app.debug=False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://u5koc5pmsi04m:pa6d6513f133fcb854a9f43c40440fbac162edddc88faafe056c3ee9bd0acfd2b@ceu9lmqblp8t3q.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dbtuol013u1r34'

db = SQLAlchemy(app)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

class Image(db.Model):
    __tablename__ = 'image'
    id = db.Column(db.Integer, primary_key=True)
    input_image_path = db.Column(db.String(255))
    detected_image_path = db.Column(db.String(255))
    knots_detected = db.Column(db.Integer)

    def __init__(self, input_image_path, detected_image_path, knots_detected):
        self.input_image_path = input_image_path
        self.detected_image_path = detected_image_path
        self.knots_detected = knots_detected

# Directory to store uploaded images
UPLOAD_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

OUTPUT_FOLDER = os.path.join('runs', 'detect')
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

def run_yolov8(image_path):
    # Run YOLOv8 inference and save the output to the 'detections.txt' file
    cmd = ['yolo', 'task=detect', 'mode=predict', 'model=yolov8_checkpoint_rugs.pt', 'conf=0.25', f'source={image_path}','show_labels=False','show_conf=False','save_txt=True','max_det=800', 'iou=0.05']
    subprocess.run(' '.join(cmd), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def highest_directory(path):
    dirs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    if not dirs:
        return None
    numeric_dirs = [int(d.split('predict')[-1]) for d in dirs if d.startswith('predict') and d != 'predict']
    if not numeric_dirs:
        return 'predict'
    return 'predict' + str(max(numeric_dirs))

def count_knots_in_labels(file_path):
    with open(file_path, 'r') as f:
        total_knots = sum(1 for line in f)
    return total_knots

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return redirect(request.url)
    
    file = request.files['image']

    if file.filename == '':
        return redirect(request.url)

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        # Run YOLOv8 inference
        run_yolov8(file_path)
        # Construct paths for input and detected images
        input_image_path = file_path
        highest = highest_directory(OUTPUT_FOLDER)

        detected_image_path = OUTPUT_FOLDER + "/" + highest + "/" + filename

        with open(detected_image_path, "rb") as img_file:
            # Convert binary data to base64 encoding
            binary_data = base64.b64encode(img_file.read()).decode('utf-8')

        filename_without_extension = os.path.splitext(filename)[0]
        # Creating the new label filename with .txt extension
        label_filename = filename_without_extension + ".txt"
        label_file_path = os.path.join(OUTPUT_FOLDER, highest, "labels", label_filename)
        
        knots_detected = count_knots_in_labels(label_file_path)

        print("Total number of Knots Detected",knots_detected)
        print("highest predict directory",highest)
        print("label filename", label_filename)
        print("label file path",label_file_path)
        print("input filename",filename)
        print("input image path",input_image_path)
        print("detected image path",detected_image_path)

        # Upload images to Cloudinary
        cloudinary.config( 
            cloud_name = "dc2kozksq", 
            api_key = "912975253421356", 
            api_secret = "yA2UKS8DgQp_gSzOEyJ10JuGVCY" 
        )

        # Generate unique public IDs based on the current timestamp
        input_public_id = f"input_image_{int(time.time())}"
        detected_public_id = f"detected_image_{int(time.time())}"

        input_cloudinary_url = uploader.upload(input_image_path, public_id=input_public_id)['secure_url']
        detected_cloudinary_url = uploader.upload(detected_image_path, public_id=detected_public_id)['secure_url']

        image_entry = Image(input_image_path=input_cloudinary_url, detected_image_path=detected_cloudinary_url, knots_detected=knots_detected)
        db.session.add(image_entry)
        db.session.commit()

        return render_template('index.html', input_image=input_image_path, detected_image_binary=binary_data, knots_detected=knots_detected)

if __name__ == '__main__':
    app.run(debug=True)
