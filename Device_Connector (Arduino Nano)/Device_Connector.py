import time
import json
from MyMQTT import MyMQTT
from Sensors import SoilMoistureSen, DHT22Sen, LightSen, RainSen, WaterFlowSen

class DeviceConnector:
    def __init__(self, config_file):
        """
        Initialize the DeviceConnector class, load the configuration file and set up the sensor.
        """
        self.config = self.load_config(config_file)
        self.clientID = self.config['clientID']
        self.base_topic = self.config['baseTopic']
        self.mqtt_client = MyMQTT(self.clientID, broker='mqtt.eclipseprojects.io', port=1883, notifier=None)
        self.mqtt_client.start()
        self.sensors = self.initialize_sensors()

    def load_config(self, file_path):
        """
        Load configuration from a JSON file.
        """
        with open(file_path, 'r') as file:
            return json.load(file)

    def initialize_sensors(self):
        """
        Initialize all sensor objects.
        """
        sensors = []
        for device in self.config['devicesList']:
            if 'soil_moisture' in device['measureType']:
                sensors.append(SoilMoistureSen(device['deviceID'], device['servicesDetails'][0]['topic']))
            elif 'temperature' in device['measureType'] or 'humidity' in device['measureType']:
                sensors.append(DHT22Sen(device['deviceID'], device['servicesDetails'][0]['topic']))
            elif 'light' in device['measureType']:
                sensors.append(LightSen(device['deviceID'], device['servicesDetails'][0]['topic']))
            elif 'rain' in device['measureType']:
                sensors.append(RainSen(device['deviceID'], device['servicesDetails'][0]['topic']))
            elif 'water_flow' in device['measureType']:
                sensors.append(WaterFlowSen(device['deviceID'], device['servicesDetails'][0]['topic']))
        return sensors

    def collect_and_publish_data(self):
        """
        Collect sensor data and publish it via MQTT.
        """
        for sensor in self.sensors:
            sensor_data = sensor.read()

            if isinstance(sensor_data, tuple):
                light_level, timestamp = sensor_data
                message = self.create_message(sensor.device_id, light_level, 'lux', timestamp)
            else:
                if isinstance(sensor, SoilMoistureSen):
                    message = self.create_message(sensor.device_id, sensor_data, '%')
                elif isinstance(sensor, DHT22Sen):
                    temp_message = self.create_message(sensor.device_id, sensor_data['temperature'], '°C')
                    humidity_message = self.create_message(sensor.device_id, sensor_data['humidity'], '%')
                    self.mqtt_client.myPublish(sensor.topic[0], temp_message)
                    print(f"Publish a message to a topic {sensor.topic[0]}: {temp_message}")
                    self.mqtt_client.myPublish(sensor.topic[1], humidity_message)
                    print(f"Publish a message to a topic {sensor.topic[1]}: {humidity_message}")
                    continue
                elif isinstance(sensor, RainSen):
                    message = self.create_message(sensor.device_id, sensor_data, 'unknown')
                elif isinstance(sensor, WaterFlowSen):
                    message = self.create_message(sensor.device_id, sensor_data, 'L/min')
                else:
                    message = self.create_message(sensor.device_id, sensor_data, 'unknown')

            topic = sensor.topic[0] if isinstance(sensor.topic, list) else sensor.topic
            self.mqtt_client.myPublish(topic, message)
            print(f"Publish a message to a topic {topic}: {message}")

    def create_message(self, device_id, data, unit, timestamp=None):
        """
        Create a structured message for publishing, containing sensor data and unit information.
        """
        if timestamp is None:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

        msg = {
            "bn": f"{self.base_topic}/sensors/{self.clientID}/{device_id}",
            "e": [{
                "n": f"sensor_{device_id}",
                "v": data,
                "u": unit,
                "t": timestamp
            }]
        }
        return msg

    def run(self):
        try:
            while True:
                self.collect_and_publish_data()
                time.sleep(600)  # Publish data from all sensors every 10 minutes
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """
        Stop the MQTT client.
        """
        self.mqtt_client.stop()


if __name__ == '__main__':
    config_file = 'setting_sen.json'
    device_connector = DeviceConnector(config_file)
    device_connector.run()

