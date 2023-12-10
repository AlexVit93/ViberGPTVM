from datetime import datetime
import logging
import os
import g4f
from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest, ViberSubscribedRequest

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///viber_requests.db'
db = SQLAlchemy(app)

class UserRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, unique=True, nullable=False)
    last_request_token = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

viber = Api(BotConfiguration(
    name='Чат Йопите ГГТУ',
    avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
    auth_token="521050f57467dfbf-f45b9b21ace92422-5e8da79493cf619c"
))


@app.route('/viber-webhook', methods=['POST'])
def incoming():
    logging.debug(f"{datetime.now()}: received request. post data: {request.get_data()}")

    if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
        logging.error("Invalid signature")
        return Response(status=403)

    viber_request = viber.parse_request(request.get_data())
    message_token = getattr(viber_request, 'message_token', None)
    user_id = getattr(viber_request.sender, 'id', None)

    if isinstance(viber_request, ViberConversationStartedRequest):
        viber.send_messages(user_id, [
            TextMessage(text="Салют! Это наш чат Йопите, ну ты понял/а) Чем я могу тебе помочь сегодня?")
        ])
    elif isinstance(viber_request, ViberSubscribedRequest):
        viber.send_messages(user_id, [
            TextMessage(text="Thanks for subscribing!")
        ])
    elif isinstance(viber_request, ViberMessageRequest):
        process_message_request(viber_request, user_id, message_token)
    elif isinstance(viber_request, ViberFailedRequest):
        logging.error("Message failed")

    return Response(status=200)

def process_message_request(viber_request, user_id, message_token):
    existing_request = UserRequest.query.filter_by(user_id=user_id).first()

    if existing_request and existing_request.last_request_token == message_token:
        logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored for user {user_id}.")
        return

conversation_history = {}

def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while history and current_length > max_length:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history
  
def message_received_callback(viber_request):
    user_id = viber_request.sender.id
    user_input = viber_request.message.text
    message_token = getattr(viber_request, 'message_token', None)

    logging.info(f"{datetime.now()}: Received message from {user_id}: {user_input}")

    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({"role": "user", "content": user_input})
    conversation_history[user_id] = trim_history(conversation_history[user_id])

    chat_history = conversation_history[user_id]

    existing_request = UserRequest.query.filter_by(user_id=user_id).first()

    if existing_request and existing_request.last_request_token == message_token:
        logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored for user {user_id}.")
        return

    # Обновление или создание новой записи в базе данных
    if existing_request:
        existing_request.last_request_token = message_token
        existing_request.timestamp = datetime.utcnow()
    else:
        new_request = UserRequest(user_id=user_id, last_request_token=message_token)
        db.session.add(new_request)

    db.session.commit()
    
    # Логика для обработки сообщений пользователя с использованием g4f
    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=[{"role": "user", "content": user_input}],
            provider=g4f.Provider.GeekGpt,
        )

        logging.info(f"{datetime.now()}: g4f response: {response}")
        
        if isinstance(response, dict) and 'choices' in response and response['choices']:
            chat_gpt_response = response['choices'][0]['message']['content']
        else:
            chat_gpt_response = "Извините, произошла ошибка."
    except Exception as e:
        logging.error(f"{datetime.now()}: Error while calling g4f API: {e}")
        chat_gpt_response = "Извините, произошла ошибка при обработке вашего запроса."

    viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])
    logging.info(f"{datetime.now()}: Response sent for message token: {message_token}")

if __name__ == "__main__":
    db.create_all()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)