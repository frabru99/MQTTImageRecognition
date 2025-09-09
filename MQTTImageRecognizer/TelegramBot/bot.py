import logging
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update, Chat, InputFile
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, ApplicationBuilder, MessageHandler, filters
from threading import Thread
import time
import os
import json
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import asyncio
from PIL import Image
import io
import base64


load_dotenv()
client=mqtt.Client()

js = {}
loc_chat_id_list = [] #list of chat ids
loop= None #mqtt loop
application=None #bot application


### For Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)




""" on_connect

    This function represents the callback method called when the connection to the broker is enstablished.
    This allows to perform the subscription to the Topics calling "subscribingMQTT" function.
"""
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("MQTT client connected successfully.")
        subscribingMQTT()
    else:
        logging.error(f"MQTT connection failed with code {rc}")


""" on_message

    This function represents the callback method called when a message is received by the client from any Topic.
    In this case, the elaboration dedicated to the message is strictly correlated to the Topic.
"""
def on_message(client, userdata, msg):
    global loc_chat_id_list, application, loop


    if msg.topic == "photo/ack":
        logging.info("Message arrived on photos/ack")
        for id in loc_chat_id_list:
            asyncio.run_coroutine_threadsafe(application.bot.send_message(id, "✅🔀  Message consumed correctly by ESP32-CAM"), loop)

    elif msg.topic == "photo/response":
        logging.info("Message arrived on photos/response")
        for id in loc_chat_id_list:
            msg_json=json.loads(msg.payload.decode('utf-8'))

            mesg= f"The analsys has recogised {msg_json['count']} objects: \n" 
            for key in msg_json.keys():
                if key.startswith("object"):
                    mesg += f"- {msg_json[key]} \n"
                elif key.startswith("description"):
                    mesg += f"\n\nDescription: \n{msg_json[key]}"
            asyncio.run_coroutine_threadsafe(application.bot.send_message(id, f"💬  Response received from the serve: \n\n{mesg}"), loop)

    elif msg.topic == "photo/upload":
        logging.info("Message arrived on photos/upload")

        image_buffer = io.BytesIO(msg.payload)
        
        with Image.open(image_buffer) as img:
            output_buffer = io.BytesIO() 
            img.save(output_buffer, format="JPEG")
            output_buffer.seek(0)

            for id in loc_chat_id_list:
                asyncio.run_coroutine_threadsafe(application.bot.send_photo(id, photo=InputFile(output_buffer, filename="photo.jpg")), loop)

    elif msg.topic == "photo/nack":
        logging.info("Message arrived on photos/nack")
        for id in loc_chat_id_list:
            asyncio.run_coroutine_threadsafe(application.bot.send_message(id, "❌🔀  Message not consumed correctly by ESP32-CAM"), loop)


""" setupMQTT

    This function has the purpose to setup the client: setting callbacks, reconnection delay
    and connection to the MQTT Broker.
    
"""
            
def setupMQTT():
    global client
    client.on_message=on_message
    client.on_connect = on_connect 
    client.reconnect_delay_set(min_delay=1, max_delay=1200)
    client.connect("localhost", 1883, 60)  #host, port, keep-alive time


""" subscribingMQTT

    This function calls the .subscribe method, 
    in order to subscribe the client to topics. 
"""
def subscribingMQTT():
    global client
    client.subscribe("photo/ack")
    client.subscribe("photo/nack")
    client.subscribe("photo/response")
    client.subscribe("photo/upload")



""" write_ids

    Naive method to take trace of the ids of the connected chats to the bot, in a single file.
    This file is subsequently used to send messages to all chats connected to the bot.
    (The bot is intended for personal use.)
"""
def write_ids(update):
    global loc_chat_id_list
    
    if update.message.chat_id not in loc_chat_id_list:
        loc_chat_id_list.append(update.message.chat_id)

    with open("chat_id_list.txt", "w") as file:
    
       for id in loc_chat_id_list:
           file.write(str(id))
           file.write("\n")

            
""" start

    This function allow the bot to react to "/start" command sent in the chat by the user
    in order to activate it.
    The response is composed by a "Keyboard Markup Reply", containing only a single button 
    to send the command to shoot a photo.
"""
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    write_ids(update)
      
    keyboard = [
        [
            KeyboardButton("📸 Shoot photo"),
        ]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text("When you're ready, click the button below to shoot a photo.", reply_markup=reply_markup)


""" handle_response

    This function handles the behaviour of the buttons of the Keyboard Markup when pressed.
    In this case, it handles the bhevaiour of the single "Shoot Photo" button and the fallback message
    for the text messages sent by the user.
"""
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    user_choice = update.message.text
    global js
    global client
    global logger
    write_ids(update)

    # Controllo della scelta dell'utente e risposta corrispondente
    if user_choice == "📸 Shoot photo":

        try:
            info = client.publish("photo/command", "photo")

            await update.message.reply_text("Sending command to shoot photos...")

            info.wait_for_publish(0.1)
            if(info.is_published()):
                logger.info("Message correctly published.")
                await update.message.reply_text("✅ Message correctly published. \n\n ⏳ Waiting for response...")
                await asyncio.sleep(1.5)
            else:
                logger.error("Message not published.")
                await update.message.reply_text("❌ Message not published due problems (waited for too long).")

        except Exception:
            logger.error("Message not published.")
            await update.message.reply_text("❌ Message not published due some problems (probably the broker is down).")

            try:
                client.reconnect()
            except ConnectionRefusedError:
                logger.error("Broker not available.")
    else:
        await update.message.reply_text("Choose an option by the menu showed below. If it's not showing, press /start")



""" main
 
    In the main function, the application object is created, and initialized. Futhermore setupMQTT
    is called to initialize the client, and the main event loop is started by client.loop_start. 
    The loop global varibale is initialized with asyncio loop in order to send response messages. 
    
    After that, the main loop of the application is started calling application.run_polling()
"""
def main():
    global application, loop

    application = ApplicationBuilder().token(os.getenv('TOKEN')).build()
    

    ### Handlers for the bot
    start_handler = CommandHandler('start', start)

    application.add_handler(start_handler)

    response_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response)
    application.add_handler(response_handler)

    try:
        ### Setup of MQTT and loop for asyncio 
        setupMQTT()
        client.loop_start()

    
        loop = asyncio.get_event_loop()
         
        application.run_polling()

        
    except KeyboardInterrupt as e:
        logger.info("Exiting app")
        client.loop_stop()

    


if __name__=="__main__":
    main()
