from datetime import datetime
import logging
import os
from flask import Flask, request, Response
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest, ViberSubscribedRequest
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

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

def save_message(user_id, role, content):
    conversation = session.get(Conversation, user_id)
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
    conversation = session.get(Conversation, user_id)
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

@app.route('/viber-webhook', methods=['POST'])
def incoming():
    logging.debug(f"{datetime.now()}: received request. post data: {request.get_data()}")
    
    viber_request = viber.parse_request(request.get_data())
    message_token = getattr(viber_request, 'message_token', None)

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

    return Response(status=200)

def message_received_callback(viber_request):
    user_id = viber_request.sender.id
    user_input = viber_request.message.text
    logging.info(f"{datetime.now()}: Received message from {user_id}: {user_input}")

    # Save user message to the database
    save_message(user_id, 'user', user_input)

    # Простая реализация в качестве заглушки для ответа бота
    chat_gpt_response = "Простите, у меня сейчас нет ответа."

    viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])
    
    # Save assistant's message to the database
    save_message(user_id, 'assistant', chat_gpt_response)
    logging.info(f"{datetime.now()}: Response sent for message token: {viber_request.message_token}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)
