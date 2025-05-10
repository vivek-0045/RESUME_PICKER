from flask import Flask, render_template, request, send_file
from dotenv import load_dotenv
import boto3
import os
import chardet
import PyPDF2
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
BUCKET_NAME = "resumestorer12"
REGION =  "ap-south-1"

app = Flask(__name__)

# Initialize S3 Client
s3 = boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)

def extract_text_from_pdf(pdf_bytes):
    """Extracts text from a PDF file directly from memory."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text.lower()

def decode_file(file_bytes):
    """Safely decode text files in memory."""
    detected_encoding = chardet.detect(file_bytes)["encoding"]
    return file_bytes.decode(detected_encoding or "utf-8", errors="ignore").lower()

@app.route("/", methods=["GET", "POST"])
def index():
    matched_resumes = None  # Ensure resumes list is empty initially

    if request.method == "POST":
        matched_resumes = []  # Start filtering when POST request occurs
        keyword = request.form["keyword"].lower()

        # Upload resumes to S3
        if "resumes" in request.files:
            resume_files = request.files.getlist("resumes")  # Handle multiple resumes
            for resume in resume_files:
                s3.upload_fileobj(resume, BUCKET_NAME, resume.filename)

        # Retrieve and filter all resumes from S3 **WITHOUT SAVING LOCALLY**
        objects = s3.list_objects_v2(Bucket=BUCKET_NAME)
        if "Contents" in objects:
            for obj in objects["Contents"]:
                file_name = obj["Key"]

                try:
                    # Get file object directly from S3
                    file_obj = s3.get_object(Bucket=BUCKET_NAME, Key=file_name)
                    file_bytes = file_obj["Body"].read()
                    
                    resume_text = ""

                    # Process PDFs differently from text files
                    if file_name.endswith(".pdf"):
                        resume_text = extract_text_from_pdf(file_bytes)
                    else:
                        resume_text = decode_file(file_bytes)

                    if keyword in resume_text:
                        matched_resumes.append(file_name)  # Only keep matched resumes

                except Exception as e:
                    print(f"Error processing {file_name}: {e}")

    return render_template("index.html", resumes=matched_resumes)

@app.route("/download/<filename>")
def download_file(filename):
    """Retrieve and allow download of a resume from S3."""
    try:
        file_obj = s3.get_object(Bucket=BUCKET_NAME, Key=filename)
        return send_file(BytesIO(file_obj["Body"].read()), as_attachment=True, download_name=filename)
    except Exception as e:
        print(f"Error retrieving file {filename}: {e}")
        return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True, port=5003)