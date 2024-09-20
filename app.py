from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
from core import FriendGPT
from dotenv import load_dotenv
import openai

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

# Initialize the FriendGPT object globally
friend_gpt = FriendGPT()

@app.route('/whatsapp', methods=['POST'])
def whatsapp_bot():
    # Get the incoming message body from WhatsApp
    incoming_msg = request.form.get('Body', '').strip()
    
    # Call FriendGPT to generate a response
    gpt_response = friend_gpt.chat(incoming_msg)
    
    # Create a Twilio response object
    twilio_resp = MessagingResponse()

    # Add the GPT response as the reply message
    twilio_resp.message(gpt_response)

    # Return the Twilio response as a string to WhatsApp
    return str(twilio_resp), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
