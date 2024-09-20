from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route('/whatsapp', methods=['POST'])
def whatsapp_bot():
    print("---- Incoming Twilio Request ----")
    print("Headers: ", request.headers)
    print("Form Data: ", request.form)
    
    # Get the incoming message body
    incoming_msg = request.form.get('Body', '').strip()

    # Create a Twilio response object
    twilio_resp = MessagingResponse()
    
    # Add a reply message
    reply_msg = twilio_resp.message(f"Your message was: {incoming_msg}")
    
    # Return the Twilio response as a string
    return str(twilio_resp), 200

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
