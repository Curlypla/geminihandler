import time
import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from collections import deque
from threading import Lock

app = Flask(__name__)

# Configuration
API_KEYS = os.getenv("API_KEYS").split(",")  # Comma-separated list of API keys
USES_PER_MINUTE = 2
RESET_INTERVAL = 60  # seconds
MAX_RETRIES = 3

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
    models = ['gemini-1.5-pro-latest', 'gemini-1.5-pro-latest', 'gemini-1.5-flash']
    temperatures = [1.0, 0.5, 1.0]  # Default, lower temperature, default for flash model

    for attempt in range(MAX_RETRIES):
        try:
            api_key = key_manager.get_available_key()
            print(f"Using key: {api_key}, Attempt: {attempt + 1}, Model: {models[attempt]}, Temperature: {temperatures[attempt]}")
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(models[attempt])
            
            generation_config = {"temperature": temperatures[attempt]}
            response = model.generate_content(prompt, generation_config=generation_config, request_options={"timeout": 600})
            
            print(f"Request successful on attempt {attempt + 1}")
            print(response.text)
            print(response.candidate.safety_ratings)
            return response.text
        except Exception as e:
            if attempt == MAX_RETRIES - 1:  # If this was the last attempt
                return f"Error after {MAX_RETRIES} attempts: {str(e)}"
            time.sleep(1)  # Wait a bit before retrying
    
    # This line should never be reached, but just in case:
    return "Unexpected error occurred"

# hello world route
@app.route('/')
def hello_world():
    return 'zhy'

@app.route('/generate', methods=['POST'])
def generate():
    prompt = request.json.get('prompt')
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    response = get_gemini_response(prompt)
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run()
