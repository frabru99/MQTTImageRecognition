import logging
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update, Chat
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, ApplicationBuilder, MessageHandler, filters
from threading import Thread
import time
import os
import json
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import asyncio

load_dotenv()
client=mqtt.Client()

js = {}
loc_chat_id_list = [] #list of chat ids
application = ApplicationBuilder().token(os.getenv('TOKEN')).build() #application for the bot
loop=0 #mqtt loop


### For Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


### Callback for messages on the topics
def on_message(client, userdata, msg):
    global loc_chat_id_list, application, loop

    if msg.topic == "photo/ack":
        logging.info("Message arrived on photos/ack")
        for id in loc_chat_id_list:
            asyncio.run_coroutine_threadsafe(application.bot.send_message(id, "🔀  Message consumed correctly by ESP32-CAM"), loop)
    elif msg.topic == "photo/response":
        logging.info("Message arrived on photos/response")
        for id in loc_chat_id_list:
            mesg=msg.payload.decode('utf-8')
            asyncio.run_coroutine_threadsafe(application.bot.send_message(id, f"💬  Response received from the server: \n\n {mesg}"), loop)
     
### MQTT setup
def setupMQTT():
    global client
    client.on_message=on_message
    client.connect("localhost", 1883, 60)  #host, port, keep-alive time
    clientThread=mqtt.Client()
    client.subscribe("photo/ack")
    client.subscribe("photo/response")
    client.loop_start()

### Writing of chat ids        
def write_ids(update):
    global loc_chat_id_list
    
    if update.message.chat_id not in loc_chat_id_list:
        loc_chat_id_list.append(update.message.chat_id)

    with open("chat_id_list.txt", "w") as file:
    
       for id in loc_chat_id_list:
           file.write(str(id))
           file.write("\n")

            
### Start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    write_ids(update)
      
    keyboard = [
        [
            KeyboardButton("📸 Shoot photo"),
        ]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text("When you're ready, click the button below to shoot a photo.", reply_markup=reply_markup)


### Handler for responses by the user
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
                await update.message.reply_text("✅ Message correctly published.")
                time.sleep(1.5)
                await update.message.reply_text("Waiting for response...")
            else:
                logger.error("Message not published.")
                await update.message.reply_text("❌ Message not published due problems (waited but not published).")

        except Exception:
            logger.error("Message not published.")
            await update.message.reply_text("❌ Message not published due some problems (probably the broker is down).")

            try:
                setupMQTT()
            except ConnectionRefusedError:
                logger.error("Broker not available.")
    else:
        await update.message.reply_text("Choose an option by the menu showed below. If it's not showing, press /start")


def main():
    global application, loop

    ### Handlers for the bot
    start_handler = CommandHandler('start', start)

    application.add_handler(start_handler)

    response_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response)
    application.add_handler(response_handler)

    ### Setup of MQTT and loop for asyncio 
    setupMQTT()
    loop = asyncio.get_event_loop()   
    application.run_polling()
    
    client.loop_stop()


if __name__=="__main__":
    main()
