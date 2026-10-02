import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()  # reads .env file into environment variables

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# API key is read from the environment, never hardcoded here.
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/service-worker.js")
def service_worker():
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, "service-worker.js", mimetype="application/javascript")


@app.route("/api/ask", methods=["POST"])
def ask():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files["image"]
    question = request.form.get("question", "What is in this image?").strip()

    if image_file.filename == "":
        return jsonify({"error": "No image selected"}), 400

    if not allowed_file(image_file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    ext = image_file.filename.rsplit(".", 1)[1].lower()
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    saved_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_name)
    image_file.save(saved_path)

    try:
        img = Image.open(saved_path)
        response = model.generate_content([question, img])
        answer_text = response.text
    except Exception as e:
        return jsonify({"error": f"AI request failed: {str(e)}"}), 500

    return jsonify({"answer": answer_text})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
