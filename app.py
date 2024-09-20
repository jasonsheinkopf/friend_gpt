import os
from flask import Flask, request

app = Flask(__name__)

@app.route('/whatsapp', methods=['POST'])
def whatsapp_bot():
    print("---- Incoming Twilio Request ----")
    print("Headers: ", request.headers)
    print("Form Data: ", request.form)
    
    # Return a simple response to check connectivity
    return "Message received", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Get the port from environment variable or default to 5000
    app.run(host="0.0.0.0", port=port, debug=True)  # Bind to 0.0.0.0 to accept external requests
