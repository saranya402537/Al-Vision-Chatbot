import os
import base64
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
import anthropic

load_dotenv()  # reads .env file into environment variables

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# API key is read from the environment, never hardcoded here.
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_media_type(filename):
    ext = filename.rsplit(".", 1)[1].lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }[ext]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/service-worker.js")
def service_worker():
    # Served from the root (not /static/) so its scope covers the whole app,
    # letting it control the main page instead of just /static/*.
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, "service-worker.js", mimetype="application/javascript")


@app.route("/api/ask", methods=["POST"])
def ask():
    """
    Expects multipart/form-data with:
      - image: the uploaded file
      - question: the user's text question
    Returns JSON: { "answer": "..." }
    """
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files["image"]
    question = request.form.get("question", "What is in this image?").strip()

    if image_file.filename == "":
        return jsonify({"error": "No image selected"}), 400

    if not allowed_file(image_file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    # Save a copy (optional, useful for debugging / history later)
    ext = image_file.filename.rsplit(".", 1)[1].lower()
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    saved_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_name)
    image_file.save(saved_path)

    # Read the saved file back and base64-encode it for the API
    with open(saved_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    media_type = get_media_type(image_file.filename)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": question},
                    ],
                }
            ],
        )
        answer_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
    except Exception as e:
        return jsonify({"error": f"AI request failed: {str(e)}"}), 500

    return jsonify({"answer": answer_text})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
