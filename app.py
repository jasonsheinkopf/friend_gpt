from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Root route to handle general access
@app.route('/')
def home():
    return "Welcome to the WhatsApp bot!"

# Route to handle WhatsApp messages
@app.route('/whatsapp', methods=['POST'])
def whatsapp_bot():
    print("---- Incoming Twilio Request ----")
    print("Headers: ", request.headers)
    print("Form Data: ", request.form)
    
    incoming_msg = request.form.get('Body', '').strip()

    # Create a response
    twilio_resp = MessagingResponse()
    reply_msg = twilio_resp.message(f"Your message was: {incoming_msg}")
    
    return str(twilio_resp), 200

if __name__ == '__main__':
    app.run(debug=True)
