import random  # For simulation data
from datetime import datetime

class SoilMoistureSen:
    def __init__(self, device_id, topic, min_moisture=20, max_moisture=80):
        """
        Initialize the soil moisture sensor simulation.
        """
        self.device_id = device_id
        self.topic = topic
        self.min_moisture = min_moisture
        self.max_moisture = max_moisture

    def read(self):
        """Simulates reading soil moisture sensor data and returns the current humidity value"""
        return random.uniform(self.min_moisture, self.max_moisture)

class DHT22Sen:
    def __init__(self, device_id, topic, min_temp=-10, max_temp=40, min_humidity=20, max_humidity=90):
        """
        Simulates reading soil moisture sensor data and returns the current humidity value
        """
        self.device_id = device_id
        self.topic = topic
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.min_humidity = min_humidity
        self.max_humidity = max_humidity

    def read(self):
        """Simulates reading temperature and humidity sensor data and returns the current temperature and humidity"""
        return {
            'temperature': random.uniform(self.min_temp, self.max_temp),
            'humidity': random.uniform(self.min_humidity, self.max_humidity)
        }

class LightSen:
    def __init__(self, device_id, topic, min_light=0, max_light=1000):
        """
        Initializes the light sensor simulation.
        """
        self.device_id = device_id
        self.topic = topic
        self.min_light = min_light
        self.max_light = max_light

    def read(self):
        """Simulates reading of light sensor data and returns the current light intensity"""
        light_level = random.uniform(self.min_light, self.max_light)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return light_level, timestamp

class RainSen:
    def __init__(self, device_id, topic, max_rain_level=10.0):
        """
        Initializes the rain sensor simulation.
        """
        self.device_id = device_id
        self.topic = topic
        self.max_rain_level = max_rain_level

    def read(self):
        """Simulates reading of rain sensor data and returns simulated rainfall value"""
        return random.uniform(0, self.max_rain_level)

class WaterFlowSen:
    def __init__(self, device_id, topic, min_flow=0.2, max_flow=5.0):
        """
        Initialize the water flow sensor simulation.
        """
        self.device_id = device_id
        self.topic = topic
        self.min_flow = min_flow
        self.max_flow = max_flow

    def read(self):
        """Simulates reading of water flow sensor data and returns the current water flow value"""
        return random.uniform(self.min_flow, self.max_flow)

class LED:
    def __init__(self, device_id, topic):
        """
        Initialize the LED controller.
        """
        self.device_id = device_id
        self.topic = topic

    def set_state(self, state):
        """Simulate setting the LED state"""
        print(f"LED {self.device_id} set to {'ON' if state else 'OFF'}")

class WaterPump:
    def __init__(self, device_id, url, topic):
        self.device_id = device_id
        self.url = url
        self.topic = topic

    def set_state(self, state):
        """Simulates controlling the status of a water pump through a REST interface and publishing status updates through MQTT"""
        response = f"Mocked REST call to {self.url} to set state {'ON' if state else 'OFF'}"
        print(f"Water Pump {self.device_id} set to {'ON' if state else 'OFF'}")

        return response

