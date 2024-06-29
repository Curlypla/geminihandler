import time, os
from flask import Flask, request, jsonify
import google.generativeai as genai
from collections import deque
from threading import Lock
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Configuration
API_KEYS = os.getenv("API_KEYS").split(",")  # Comma-separated list of API keys
USES_PER_MINUTE = 2
RESET_INTERVAL = 60  # seconds
MAX_RETRIES = 2

class APIKeyManager:
    def __init__(self, keys):
        self.keys = deque(keys)
        self.usage = {key: {"count": 0, "last_reset": time.time()} for key in keys}
        self.lock = Lock()

    def get_available_key(self):
        while True:
            with self.lock:
                current_time = time.time()
                for _ in range(len(self.keys)):
                    key = self.keys[0]
                    if current_time - self.usage[key]["last_reset"] >= RESET_INTERVAL:
                        self.usage[key] = {"count": 0, "last_reset": current_time}
                    if self.usage[key]["count"] < USES_PER_MINUTE:
                        self.usage[key]["count"] += 1
                        return key
                    self.keys.rotate(-1)
            time.sleep(1)

key_manager = APIKeyManager(API_KEYS)

def get_gemini_response(prompt):
    for attempt in range(MAX_RETRIES):
        try:
            api_key = key_manager.get_available_key()
            print("using key:", api_key)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
            response = model.generate_content(prompt, request_options={"timeout": 600})
            return response.text
        except Exception as e:
            if attempt == MAX_RETRIES - 1:  # If this was the last attempt
                return f"Error after {MAX_RETRIES} attempts: {str(e)}"
            time.sleep(1)  # Wait a bit before retrying
    
    # This line should never be reached, but just in case:
    return "Unexpected error occurred"

@app.route('/generate', methods=['POST'])
def generate():
    prompt = request.json.get('prompt')
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    response = get_gemini_response(prompt)
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)