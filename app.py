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
    app.run(debug=True)
