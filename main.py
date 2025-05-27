
import requests
from flask import Flask, request, jsonify
import os
import time
from tempfile import NamedTemporaryFile

app = Flask(__name__)
CAPTIONS_API_KEY = os.getenv("CAPTIONS_API_KEY")

@app.route("/upload", methods=["POST"])
def upload():
    try:
        data = request.get_json()
        video_url = data.get("video_url")
        name = data.get("name", "AutoVideo")

        if not video_url:
            return jsonify({"error": "Missing video_url"}), 400

        tmp = NamedTemporaryFile(delete=False, suffix=".mp4")
        with requests.get(video_url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
        tmp.close()

        with open(tmp.name, "rb") as video_file:
            response = requests.post(
                "https://api.captions.ai/api/v1/projects",
                headers={"Authorization": f"Bearer {CAPTIONS_API_KEY}"},
                files={"file": ("video.mp4", video_file, "video/mp4")},
                data={
                    "name": name,
                    "template": "Paper",
                    "music": "true",
                    "auto_ducking": "true"
                },
            )

        if response.status_code >= 400:
            return jsonify({
                "error": "Captions.ai failed",
                "details": response.text
            }), 500

        project_id = response.json().get("id")
        status = "processing"
        output_url = None

        while status == "processing":
            time.sleep(10)
            check = requests.get(
                f"https://api.captions.ai/api/v1/projects/{project_id}",
                headers={"Authorization": f"Bearer {CAPTIONS_API_KEY}"}
            ).json()
            status = check.get("status", "")
            if status == "completed":
                output_url = check.get("video_url")
                break
            if status == "failed":
                return jsonify({"error": "Captions.ai processing failed"}), 500

        return jsonify({
            "project_id": project_id,
            "captions_video_url": output_url
        })
    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500
