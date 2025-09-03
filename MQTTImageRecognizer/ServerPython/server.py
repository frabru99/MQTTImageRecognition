from PIL import Image
import io
import paho.mqtt.client as mqtt
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()
client = mqtt.Client()
loop=0


### For Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def on_message(client, userdata, msg):
    global loop

    debug_filename = "debug_received_payload.bin"
    with open(debug_filename, "wb") as f:
        f.write(msg.payload)
    print(f"Payload grezzo salvato in '{debug_filename}' per l'analisi.")
    # =================================================================

    try:
        # Ora prova ad aprire i dati con Pillow
        image_stream = io.BytesIO(msg.payload)
        img = Image.open(image_stream)
        
        print("Pillow ha aperto l'immagine con successo!")
        # ... continua con la logica di analisi LLM ...
        #img.show()
        img.save("image.jpg")
        

    except Exception as e:
        print(f"ERRORE: Pillow non è riuscito ad aprire l'immagine.")
        print(f"   -> Dettaglio: {e}")
        print(f"   -> Controlla il file '{debug_filename}'. Qual è la sua dimensione? Riesci ad aprirlo con un visualizzatore di immagini?")
    


### MQTT setup
def setupMQTT():
    global client
    client.on_message=on_message
    client.connect("localhost", 1883, 60)  #host, port, keep-alive time
    client.subscribe("photo/upload")
    client.loop_forever()


def main():
    global loop

    try:
        setupMQTT()
        loop = asyncio.get_event_loop()

    except KeyboardInterrupt:
        client.loop_stop()

if __name__=="__main__":
    main()
