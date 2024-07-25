from datetime import datetime
import logging
import os
import openai
from flask import Flask, request, Response
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from viberbot.api.viber_requests import ViberMessageRequest, ViberConversationStartedRequest, ViberFailedRequest, ViberSubscribedRequest
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import openai_api_key


def get_gpt_3_5_turbo_response(user_input):
    openai.api_key = openai_api_key
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Вы находитесь в чате с AI."},
                {"role": "user", "content": user_input},
            ]
        )
        return response.choices[0].message['content']
    except Exception as e:
        print(f"Ошибка при генерации ответа: {e}")
        return ""


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
    last_message_token = Column(String, nullable=True)
    messages = relationship('MessageHistory')


engine = create_engine('sqlite:///chatbot.db')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()


def save_message(user_id, role, content, message_token=None):
    conversation = session.query(Conversation).filter(
        Conversation.user_id == user_id).first()
    if not conversation:
        conversation = Conversation(user_id=user_id)
    message = MessageHistory(user_id=user_id, role=role, content=content)
    conversation.messages.append(message)
    if role == 'assistant':
        conversation.last_interaction_at = datetime.utcnow()
        if message_token:
            conversation.last_message_token = message_token
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
    logging.debug(
        f"{datetime.now()}: received request. post data: {request.get_data()}")

    viber_request = viber.parse_request(request.get_data())
    message_token = getattr(viber_request, 'message_token', None)

    if isinstance(viber_request, (ViberMessageRequest, ViberConversationStartedRequest, ViberSubscribedRequest)) and hasattr(viber_request, 'sender'):
        user_id = viber_request.sender.id

        if message_token:
            conversation = session.query(Conversation).filter(
                Conversation.user_id == user_id).first()
            if conversation and conversation.last_message_token == message_token:
                return Response(status=200)

        if isinstance(viber_request, ViberConversationStartedRequest):
            viber.send_messages(viber_request.user.id, [
                TextMessage(
                    text="Салют! Это наш чат Йопите, ну ты понял/а) Чем я могу тебе помочь сегодня?")
            ])
        elif isinstance(viber_request, ViberSubscribedRequest):
            viber.send_messages(viber_request.user.id, [
                TextMessage(text="Thanks for subscribing!")
            ])
        elif isinstance(viber_request, ViberMessageRequest):
            message_received_callback(viber_request)

        if message_token:
            save_message(viber_request.sender.id, 'system',
                         'Processed request', message_token)
    elif isinstance(viber_request, ViberFailedRequest):
        logging.error("Message failed")

    return Response(status=200)

def message_received_callback(viber_request):
    user_id = viber_request.sender.id
    user_input = viber_request.message.text
    logging.info(
        f"{datetime.now()}: Received message from {user_id}: {user_input}")

    save_message(user_id, 'user', user_input)

    chat_gpt_response = get_gpt_3_5_turbo_response(user_input)

    viber.send_messages(user_id, [TextMessage(text=chat_gpt_response)])

    save_message(user_id, 'assistant', chat_gpt_response)
    logging.info(
        f"{datetime.now()}: Response sent for message token: {viber_request.message_token}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True)
