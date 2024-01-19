from datetime import datetime
import logging
import os
import g4f
from flask import Flask, request, Response
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest, ViberSubscribedRequest
from threading import Lock
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class MessageHistory(Base):
    __tablename__ = 'message_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('conversation.user_id'))
    role = Column(String)
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = 'conversation'

    user_id = Column(String, primary_key=True)
    last_interaction_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship('MessageHistory')

# Инициализация движка SQLite и создание таблиц
engine = create_engine('sqlite:///chatbot.db')
Base.metadata.create_all(engine)

# Создание сессии
Session = sessionmaker(bind=engine)
session = Session()

# Ваши функции для сохранения/чтения из базы данных

def save_message(user_id, role, content):
    conversation = session.query(Conversation).get(user_id)
    if not conversation:
        conversation = Conversation(user_id=user_id)

    message = MessageHistory(user_id=user_id, role=role, content=content)
    conversation.messages.append(message)

    if role == 'assistant':
        conversation.last_interaction_at = datetime.utcnow()

    session.add(conversation)
    session.add(message)
    session.commit()

def get_last_interaction(user_id):
    conversation = session.query(Conversation).get(user_id)
    if conversation:
        return conversation.last_interaction_at
    return None

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

viber = Api(BotConfiguration(
    name='Чат Йопите ГГТУ',
    avatar='https://dl-media.viber.com/1/share/2/long/vibes/icon/image/0x0/7a08/3c87d21eceedb833743a81c19b74cea8c1c3e4ef66e7c86b71d82d16c1147a08.jpg',
    auth_token="521050f57467dfbf-f45b9b21ace92422-5e8da79493cf619c"
))


last_processed_message_token = None
token_lock = Lock()  # Создаем блокировку для потоков



@app.route('/viber-webhook', methods=['POST'])
def incoming():
    global last_processed_message_token
    logging.debug(f"{datetime.now()}: received request. post data: {request.get_data()}")
    
    if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
        logging.error("Invalid signature")
        return Response(status=403)
    
    viber_request = viber.parse_request(request.get_data())
    message_token = getattr(viber_request, 'message_token', None)
    
    if message_token and message_token == last_processed_message_token:
        logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored.")
        return Response(status=200)
    
    if isinstance(viber_request, ViberConversationStartedRequest):
        viber.send_messages(viber_request.user.id, [
            TextMessage(text="Салют! Это наш чат Йопите, ну ты понял/а) Чем я могу тебе помочь сегодня?")
        ])
    elif isinstance(viber_request, ViberSubscribedRequest):
        viber.send_messages(viber_request.user.id, [
            TextMessage(text="Thanks for subscribing!")
        ])
    elif isinstance(viber_request, ViberMessageRequest):
        message_received_callback(viber_request)
    elif isinstance(viber_request, ViberFailedRequest):
        logging.error("Message failed")
    
    last_processed_message_token = message_token
    return Response(status=200)

conversation_history = {}

def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while history and current_length > max_length:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history

SOME_TIME_LIMIT = 60 

def message_received_callback(viber_request):
    global last_processed_message_token
    with token_lock:  # Используем блокировку для безопасного доступа к глобальной переменной
        user_id = viber_request.sender.id
        user_input = viber_request.message.text
        message_token = getattr(viber_request, 'message_token', None)

        logging.info(f"{datetime.now()}: Received message from {user_id}: {user_input}")

        if message_token is None:
            logging.error("No message_token found in the request")
            return

        if message_token == last_processed_message_token:
            logging.info(f"{datetime.now()}: Duplicate message with token {message_token} received and ignored.")
            return

        # Проверяем последнее взаимодействие с пользователем, чтобы избежать дублирования ответов
        last_interaction = get_last_interaction(user_id)
        if last_interaction and (datetime.utcnow() - last_interaction).total_seconds() < SOME_TIME_LIMIT:
            logging.info("Duplicate response prevention")
            return

        # Save user message to the database
        save_message(user_id, 'user', user_input)

    chat_history = conversation_history[user_id]

    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=chat_history,
            provider=g4f.Provider.GeekGpt,
        )

        logging.info(f"{datetime.now()}: g4f response: {response}")

        if isinstance(response, dict) and 'choices' in response and response['choices']:
            chat_gpt_response = response['choices'][0]['message']['content']
        else:
            if isinstance(response, str):
                chat_gpt_response = response
            else:
                logging.error(f"{datetime.now()}: Unexpected response format or error: {response}")
                chat_gpt_response = "Извините, произошла ошибка."
    except Exception as e:
        logging.error(f"{datetime.now()}: Error while calling g4f API: {e}")
        chat_gpt_response = "Извините, произошла ошибка при обработке вашего запроса."

    viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])
    
    # Save assistant's message to the database
    save_message(user_id, 'assistant', chat_gpt_response)

    # Обновляем токен последнего обработанного сообщения
    last_processed_message_token = message_token

    logging.info(f"{datetime.now()}: Response sent for message token: {message_token}")
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)
