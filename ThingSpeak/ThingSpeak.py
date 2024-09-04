import time
import json
from statistics import mean
from MyMQTT import MyMQTT


class ThingSpeakAdapter:
    def __init__(self):
        self.local_client = MyMQTT("LocalClient", LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, self)
        self.ts_client = MyMQTT(THINGSPEAK_MQTT_CLIENT_ID, THINGSPEAK_MQTT_HOST, THINGSPEAK_MQTT_PORT, self)

        self.ts_client._paho_mqtt.username_pw_set(THINGSPEAK_MQTT_USERNAME, THINGSPEAK_MQTT_PASSWORD)

        self.data_buffer = {}
        self.soil_moisture_values = []
        self.last_send_time = 0

    def notify(self, topic, payload):
        print(f"Received message on topic {topic}: {payload.decode()}")
        try:
            payload = json.loads(payload.decode())
            event = payload["e"][0]
            value = event['v']

            if "soil_moisture" in topic:
                self.soil_moisture_values.append(value)
                if len(self.soil_moisture_values) == 9:
                    avg_soil_moisture = mean(self.soil_moisture_values)
                    self.data_buffer["field4"] = f"{avg_soil_moisture:.2f}"
                    self.soil_moisture_values.clear()
            elif "temperature" in topic:
                self.data_buffer["field3"] = f"{value:.2f}"
            elif "humidity" in topic:
                self.data_buffer["field1"] = f"{value:.2f}"
            elif "light" in topic:
                self.data_buffer["field2"] = f"{value:.2f}"
            elif "rain" in topic:
                self.data_buffer["field5"] = f"{value:.2f}"
            elif "water_flow" in topic:
                self.data_buffer["field6"] = f"{value:.2f}"

            self.send_to_thingspeak()
        except Exception as e:
            print(f"Error processing message: {e}")

    def send_to_thingspeak(self):
        current_time = time.time()
        if current_time - self.last_send_time >= 15 and self.data_buffer:  # ThingSpeak limits updates to once every 15 seconds
            payload = "&".join([f"{k}={v}" for k, v in self.data_buffer.items()])
            print(f"Sending to ThingSpeak: {payload}")
            self.ts_client.myPublish(THINGSPEAK_MQTT_TOPIC, payload)
            self.data_buffer.clear()
            self.last_send_time = current_time

    def run(self):
        self.local_client.start()
        self.local_client.mySubscribe(LOCAL_MQTT_TOPIC)

        self.ts_client.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            self.local_client.stop()
            self.ts_client.stop()

if __name__ == "__main__":
    # ThingSpeak
    THINGSPEAK_CHANNEL_ID = "2576980"
    THINGSPEAK_MQTT_HOST = "mqtt3.thingspeak.com"
    THINGSPEAK_MQTT_PORT = 1883
    THINGSPEAK_MQTT_CLIENT_ID = "DjgfMx01ABEZJxwlMQIACxQ"
    THINGSPEAK_MQTT_USERNAME = "DjgfMx01ABEZJxwlMQIACxQ"
    THINGSPEAK_MQTT_PASSWORD = "dOD7/m73t0PnYVYQjuWLZObs"
    THINGSPEAK_MQTT_TOPIC = f"channels/{THINGSPEAK_CHANNEL_ID}/publish"

    # Local MQTT
    LOCAL_MQTT_HOST = "mqtt.eclipseprojects.io"
    LOCAL_MQTT_PORT = 1883
    LOCAL_MQTT_TOPIC = "Garden/sensors/#"

    adapter = ThingSpeakAdapter()
    adapter.run()
