import json
import logging
import paho.mqtt.client as mqtt
import requests
import time

API_URL = "http://localhost:8000/api/scan"
BROKER = "test.mosquitto.org"
TOPIC = "vhackathon/sensor/+"

logging.basicConfig(level=logging.INFO, format="[MQTT] %(message)s")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info(f"Connected to {BROKER}")
        client.subscribe(TOPIC)
        logging.info(f"Subscribed to {TOPIC}")
    else:
        logging.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        logging.info(f"Received on {msg.topic}: {payload}")
        
        # Bridge to FastAPI
        response = requests.post(API_URL, json=payload, timeout=2)
        if response.status_code == 200:
            res = response.json()
            logging.info(f"API Scan OK. Risk Score: {res.get('risk_score')}, Band: {res.get('band')}")
        else:
            logging.error(f"API Error {response.status_code}: {response.text}")
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON on {msg.topic}: {msg.payload}")
    except requests.RequestException as e:
        logging.error(f"API unreachable: {e}")

def run():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="vhackathon_bridge", protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(BROKER, 1883, 60)
        logging.info("Starting MQTT bridge loop...")
        client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()
        logging.info("Disconnected")
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    run()
