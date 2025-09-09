/*
This script implements the setup and the main logic of the system hub.

In a first moment, the script initializes the screen and the MQTTClient, 
then, in the second part, it will display on the screen these three informations:
- Total photo shoot attempt, 
- Total correctly analyzed photo, 
- Total objects recognized

These data will be lost in case of shutdown or restart of the board, 
since they aren't saved in any database.
*/
#include <LiquidCrystal_I2C.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include "Wire.h"
#include <string.h>

//Some definitions for strings length to print on the screen
#define ATTEMPTS_DIM 10 
#define ANALYZED_DIM 10
#define OBJECT_DIM   9  
#define STRING_VEC_DIM 3

//This variable is useful to store the message received on TOPIC_RESPONSE, to extract the objects recognized.
JsonDocument resp;

//Struct counters
struct counters {
  int totalCount;
  int totalAnalyzed;
  int totalObjectRecognized;
};
struct counters* count =(struct counters*) malloc(sizeof(struct counters));
int* values [] = {&(count->totalCount), &(count->totalAnalyzed), &(count->totalObjectRecognized)};
char* strings[] = {"Attempts: ", "Analyzed: ", "Objects: "};


//Wifi Credentials
const char* ssid="*******";
const char* password = "*******";



//MQTT Client
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
#define BROKER_IP "********"
#define BROKER_PORT 1883
#define TOPIC_COMMAND "photo/command"
#define TOPIC_RESPONSE "photo/response"


//SCREEN
LiquidCrystal_I2C lcd(0x27, 16, 2);

/* Function: initLCD

   LCD initialization and backlight startup
*/
void initLCD(){
    lcd.init();
    lcd.backlight();
    lcd.setCursor(0,0);
}


/* Function: greetingsLCD

   A simple function to show a startup Text for ESP32_HUB on the LCD Screen.
*/
void greetingsLCD(){
  lcd.print("ImageRecognition");
  delay(500);
  lcd.setCursor(0,1);
  lcd.print("ESP32_HUB");
  delay(500);

}




/* Function: refreshLCD

   This function cycles over the values of count array, in order to write the values on 
   the screen.
*/
void refreshLCD(){
  for (int i=0; i<STRING_VEC_DIM; i++){
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print(strings[i]);
      lcd.setCursor(0,1);
      lcd.print(*(values[i]));
      delay(1500);
  }

}


/*
This is the callback function that handles the reception of messages on MQTT queues.
*/
void updateValues(const char* topic, byte* payload, unsigned int length){
    if (strcmp(topic, TOPIC_COMMAND)==0){
        *(values[0]) += 1;
        Serial.println("Total Attemps increased. ");
    } else if (strcmp(topic, TOPIC_RESPONSE)==0){
        *(values[1]) += 1;

        //deserialization fo the JSON File
        deserializeJson(resp, (const char*) payload);

        const char* objects = resp["count"];

        *(values[2]) += atoi(objects);

        Serial.println("Total Analyzed and Objects increased.");

    } else {
      Serial.println("Tipic not recognised.");
    }



}


void setupWIFI(){
  WiFi.begin(ssid, password);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    lcd.print(".");
  }

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connected!");
  delay(1000);
  lcd.clear();
  lcd.setCursor(0, 0);

}

void setupMQTT(){
  // ------ MQTT Setup -------
  mqttClient.setServer(BROKER_IP, BROKER_PORT);
  mqttClient.setCallback(updateValues);
  mqttClient.setBufferSize(90536);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("MQTT Broker...");

  while (!mqttClient.connect("ESP32-HUB")){
    lcd.print(".");
    delay(300);

  } 
    

    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("Connected!");
    mqttClient.subscribe(TOPIC_COMMAND);
    mqttClient.subscribe(TOPIC_RESPONSE);
    delay(500);
    lcd.clear();
    lcd.setCursor(0,0);

}


/* Function: setup

   In this function there are some setups before the main loop starts. 
   This function initializes:
     1. The values of count struct;
     2. The WiFi connection;
     3. The MQTT client and subscription to interested topics. 
*/

void setup() {
  // put your setup code here, to run once:
  count->totalCount=0;
  count->totalAnalyzed=0;
  count->totalObjectRecognized=0;

  Wire.begin(25,26);
  Serial.begin(115200);
  initLCD();

  greetingsLCD();
  delay(1000);

  setupWIFI();
  setupMQTT();

    
}



/* Function: loop

   The loop function manages the mqttClient loop (that checks for events on Topics),
   the LCD refresh and the reconnection for MQTT Client.
*/
void loop() {
  // put your main code here, to run repeatedly:
  refreshLCD();
  bool state = mqttClient.loop();

  if (!state){
    mqttClient.setServer(BROKER_IP, BROKER_PORT);
    setupMQTT();
  }


  delay(500);

}
