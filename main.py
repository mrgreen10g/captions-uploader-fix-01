
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
        try:
            with requests.get(video_url, stream=True, timeout=10) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
        except Exception as e:
            return jsonify({"error": "Failed to download video", "details": str(e)}), 500
        finally:
            tmp.close()

        try:
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
                    timeout=60
                )
        except Exception as e:
            return jsonify({"error": "Failed to send to Captions.ai", "details": str(e)}), 500

        if response.status_code >= 400:
            return jsonify({"error": "Captions.ai failed", "details": response.text}), 500

        try:
            project_id = response.json().get("id")
        except Exception:
            return jsonify({"error": "Invalid response from Captions.ai"}), 500

        status = "processing"
        output_url = None
        while status == "processing":
            time.sleep(10)
            try:
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
            except Exception as e:
                return jsonify({"error": "Failed to check status", "details": str(e)}), 500

        return jsonify({
            "project_id": project_id,
            "captions_video_url": output_url
        })

    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500
