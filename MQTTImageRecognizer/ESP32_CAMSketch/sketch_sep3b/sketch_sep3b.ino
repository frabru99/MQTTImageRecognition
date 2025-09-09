/**********
This sketch is intended to use with an ESP32-Camera module. 
This code initializes the Wi-fi module and implements the general logic, in order to connect the board to a MQTT Broker (Mosquitto) and
shoot an image when the dedicated command is received.  
The image will be sent to another topic in order to be consumed by a Server, it will analyze the image and publish the reponse on other topics.
***********/


#include "esp_camera.h"
#include <WiFi.h>
#include "esp_timer.h"
#include "img_converters.h"
#include "Arduino.h"
#include "fb_gfx.h"
#include "soc/soc.h" //disable brownout problems
#include "soc/rtc_cntl_reg.h"  //disable brownout problems
#include <PubSubClient.h>


//Replace with your network credentials
const char* ssid="**********";
const char* password = "********";

volatile bool take=false;

//Camera buffer
camera_fb_t* buffer = NULL;

//MQTT Client
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
#define BROKER_IP "*******"
#define BROKER_PORT 1883
#define TOPIC_COMMAND "photo/command"
#define TOPIC_ULPOAD  "photo/upload"
#define TOPIC_ACK  "photo/ack"
#define TOPIC_NACK  "photo/nack"



#define PART_BOUNDARY "123456789000000000000987654321"

// This project was tested with the AI Thinker Model, M5STACK PSRAM Model and M5STACK WITHOUT PSRAM
#define CAMERA_MODEL_AI_THINKER

#if defined(CAMERA_MODEL_AI_THINKER)
  #define PWDN_GPIO_NUM     32
  #define RESET_GPIO_NUM    -1
  #define XCLK_GPIO_NUM      0
  #define SIOD_GPIO_NUM     26
  #define SIOC_GPIO_NUM     27
  
  #define Y9_GPIO_NUM       35
  #define Y8_GPIO_NUM       34
  #define Y7_GPIO_NUM       39
  #define Y6_GPIO_NUM       36
  #define Y5_GPIO_NUM       21
  #define Y4_GPIO_NUM       19
  #define Y3_GPIO_NUM       18
  #define Y2_GPIO_NUM        5
  #define VSYNC_GPIO_NUM    25
  #define HREF_GPIO_NUM     23
  #define PCLK_GPIO_NUM     22
#else
  #error "Camera model not selected"
#endif


/* Function: callback_function

   This is the callback function, called when a message is received on the topic of interests. 
   When the message on Topic "topic/command" is received, the global bool variable "take" is setted to true. 
   In the main loop, this variable will be checked.
*/
void callback_function(char* topic, byte* payload, unsigned int length){
  take = true;
}



/* Function: take_picture
   Returns: bool
	
   This function is called to took a photo with ESP32-CAM. 
   At the start, the global variable "buffer", that is a pointer to a camera_fb_t struct, is assigned
   with a pointer to an initialized structure with the photo data.

   In case of success, the function returns true, otherwise it returns false.
*/
bool take_picture(){

  Serial.println("Taking picture!");

  buffer = esp_camera_fb_get();

  if(buffer == NULL) {
    Serial.println("Error while taking the picture!");
    return false;
  }

  Serial.println("Picture taken succesfully!");

  return true;
}



/* Function: setup

   In this function there are some setups before the main loop starts. 
   This function initializes:
     1. ESP32-CAMERA, setting parameters and resolution;
     2. The WiFi connection;
     3. The MQTT client and subscription to interested topics. 
*/
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); //disable brownout detector
 
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  
 
  setupCamera();
  setupWiFi();
  setupMQTT();

}


void setupCamera(){
	 // ------ Camera Setup -------
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG; 
  
  if(psramFound()){
    Serial.println("PSRAM founded!");
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 2;
  } else {
    Serial.println("PSRAM not founded!");
    config.frame_size = FRAMESIZE_CIF;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }
  

  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

}


void setupWiFi(){
	// ------ Wi-Fi connection -------
	  WiFi.begin(ssid, password);
	  while (WiFi.status() != WL_CONNECTED) {
	    delay(500);
	    Serial.print(".");
	  }
	  Serial.println("");
	  Serial.println("WiFi connected");
	  
	  Serial.print("IP address: ");
	  Serial.print(WiFi.localIP());
	  Serial.printf("\n");
	
}


void setupMQTT(){
  // ------ MQTT Setup -------
  mqttClient.setServer(BROKER_IP, BROKER_PORT);
  mqttClient.setCallback(callback_function);
  mqttClient.setBufferSize(90536);

  if (mqttClient.connect("ESP32-CAM")){
    
    Serial.println("Connected!");
    mqttClient.subscribe(TOPIC_COMMAND);

  } else {
    Serial.printf("Problem: %d", mqttClient.state());
    Serial.println("Failed to connect to broker.");
  }

}



/* Function: loop

   The loop function manages the mqttClient loop (that checks for events on Topics).
   If the variable "take" is setted to true, means that the command is received. 
   The ESP tries to shoot a photo, and in case of success, it will be published on the appropriate topic for the analysis.	
*/
void loop() {
  delay(1000);
  bool state = mqttClient.loop();

  if (!state){
    mqttClient.setServer(BROKER_IP, BROKER_PORT);
    setupMQTT();

  }

  if (take){
    bool is_taken = take_picture();

    if (is_taken){
        //Photo buffer and the len in bytes
        const uint8_t* pic_buf = buffer->buf;
        size_t len = buffer->len;
        Serial.printf("Length of photo is: %d", (int)len);

        bool is_published = mqttClient.publish(TOPIC_ULPOAD, pic_buf, len);

        if (is_published){
          Serial.println("Photo published correctly");
          mqttClient.publish(TOPIC_ACK, "ACK");

        } else {
          Serial.println("Photo not published correctly");
          mqttClient.publish(TOPIC_NACK, "NACK");
        }

        esp_camera_fb_return(buffer);


    } else {
      Serial.println("Photo not sent correctly");
      mqttClient.publish(TOPIC_NACK, "NACK");
  
    }

    take=false;

}
}
