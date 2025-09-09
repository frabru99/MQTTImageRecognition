from PIL import Image
import io
import paho.mqtt.client as mqtt
import asyncio
import logging
from dotenv import load_dotenv
from threading import Thread
import os 
import requests
import json
import base64
import time


load_dotenv()
client = mqtt.Client()

### For Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

### LLM Query
query = """
You're a model specified in object detection in images.

Detect all the objects in the attached photo, correlatig an emoji for each object detected, and you'll give a final count of object detected. Futhermore, you will give a SHORT description about the photo. 
Present only the final output in a structured JSON, as the example below shows. 


{
    "object1": "<emoji> Person", 
    "object2": "<emoji> TV",
    "count": "2"
    "description": "The photo shows a man watching the TV. The man stands in front of the TV in the middle of the room."
}

"""



""" send_photo

    This is the entrypoint of the Thread created in callback function "on_message". 
    The thread opens the image receieved by MQTT queue, encodes it in base64, and sends it
    to Gemini-2.5-Flash to perform an analysis. The response is extracted and published on the appropriate topic. 
"""
def send_photo():

    global query, target_size
    
    with Image.open("image.jpg") as img:
        print(f"Image has size: {img.size}")
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        img_bytes = buffered.getvalue()

    img_str = base64.b64encode(img_bytes).decode("utf-8")
    logger.info("Image encoded in Base64, sending it to LLM...")

    # LLM REQUEST
    payload = {"contents": [{ "parts":[{"text": f"{query}"}, {"inline_data": {"mime_type": "image/jpeg","data": img_str}}] }]}
    res = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", headers={'Content-Type': 'application/json', 'X-goog-api-key': os.getenv("GEMINI_KEY")}, data= json.dumps(payload))
    print(res)

    try:
        docs=json.loads(res.text)
        response_extracted_words = docs['candidates'][0]['content']['parts'][0]['text']
        res_new=response_extracted_words.replace("```json", "").replace("```", "")
        res_json=json.loads(res_new)
        print("Json received: ", res_json)

    except KeyError as e:
        logger.eroor("An error occured in LLM response. Please Retry.")
        

    is_published = client.publish("photo/response", res_new)

    if(is_published):
        logger.info("Message published correctly!")
    else:
        logger.error("Message not published.")
            


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
    This allows to take the message and delegate the elaboration in a separated Thread. 
"""
def on_message(client, userdata, msg):


    try:
        image_stream = io.BytesIO(msg.payload)
        
        #img.show()
        with Image.open(image_stream) as img:
            img.save("image.jpg")

        t = Thread(target=send_photo)
        t.start()

    except Exception as e:
        print(f"ERRORE: Pillow non è riuscito ad aprire l'immagine.")
        print(f"   -> Dettaglio: {e}")



""" setupMQTT

    This function has the purpose to setup the client: setting callbacks, reconnection delay
    and connection to the MQTT Broker.
    
"""
### MQTT setup
def setupMQTT():
    global client
    client.on_connect=on_connect
    client.on_message=on_message
    client.reconnect_delay_set(min_delay=1, max_delay=1200)
    client.connect("localhost", 1883, 60)  #host, port, keep-alive time


""" subscribingMQTT

    This function calls the .subscribe method, 
    in order to subscribe the client to topics. 
"""
def subscribingMQTT():
    global client
    client.subscribe("photo/upload")


""" main
 
    In the main function, setupMQTT is called to initialize the client object. 
    After that, the main loop is started through client.loop_start.
"""
def main():
    global loop

    try:
        setupMQTT()
        client.loop_start()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        client.loop_stop()

if __name__=="__main__":
    main()
