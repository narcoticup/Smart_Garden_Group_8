import json
import time
import threading
from datetime import datetime
from MyMQTT import MyMQTT
import cherrypy
import requests

class ControlUnit:
    def __init__(self, broker, port, base_url):
        self.clientID = "CentralControlUnit"
        self.broker = broker
        self.port = port
        self.topic_prefix = "Garden/sensors/"
        self.rest_api_base_url = base_url
        self.catalog_url = "http://127.0.0.1:8080/garden"  # HomeCatalog URL

        self.client = MyMQTT(self.clientID, self.broker, self.port, self)
        self.client.start()

        # Threshold setting
        self.moisture_threshold = 30  # Soil moisture threshold
        self.temperature_threshold = [4, 30]  # Safe temperature range
        self.rain_detected_level = 4  # Rain detection threshold
        self.do_not_water_temp = 4  # Do not water below this temperature
        # Sunrise detection related
        self.SUNRISE_LUX = 100
        self.SUNRISE_BUFFER = 60  # One hour before sunrise (60 minutes)
        self.sunrise_counter = 0
        self.is_sunrise_time = False
        self.last_check_time = datetime.now()

        # Sensor data storage
        self.soil_moisture_values = {}
        self.temperature = None
        self.humidity = None
        self.light_level = None
        self.rain_level = None
        self.water_flow = None

        # Irrigation control and water usage tracking
        self.irrigation_duration = 30  # Irrigation duration (seconds)
        self.irrigation_timer = None
        self.irrigation_start_time = None
        self.irrigation_water_used = 0
        self.last_water_flow_time = time.time()
        self.total_water_used = self.load_water_usage()
        self.current_water_flow = 0

        # Status flags
        self.led_warning_state = False
        self.irrigation_in_progress = False
        self.data_collection_in_progress = False
        self.has_irrigated_today = False

        # Data count
        self.data_count = 0
        self.total_sensors = 14  # 9 soil moisture + temperature + humidity + light + rain + water flow

        # Synchronous event
        self.irrigation_complete = threading.Event()

        self.client.mySubscribe(self.topic_prefix + "#")

    def load_water_usage(self):
        try:
            with open('water_usage.json', 'r') as f:
                data = json.load(f)
                return data.get('total_water_used', 0)
        except FileNotFoundError:
            return 0

    def save_water_usage(self):
        data = {
            'total_water_used': round(self.total_water_used, 4),
            'last_updated': datetime.now().isoformat()
        }
        with open('water_usage.json', 'w') as f:
            json.dump(data, f, indent=2)
            print(f"Water usage data has been saved. Total water usage: {self.total_water_used:.4f} liters")

    def notify(self, topic, payload):
        if not self.data_collection_in_progress:
            return  #If not in the data collection phase, ignore the incoming data

        try:
            msg = json.loads(payload)
            sensor_data = msg["e"][0]
            value = sensor_data["v"]

            if "soil_moisture" in topic:
                sensor_id = topic.split('/')[-1]
                self.handle_soil_moisture(sensor_id, value)
            elif "temperature" in topic:
                self.handle_temperature(value)
            elif "humidity" in topic:
                self.handle_humidity(value)
            elif "light" in topic:
                self.handle_light(value)
            elif "rain" in topic:
                self.handle_rain(value)
            elif "water_flow" in topic:
                self.handle_water_flow(value)

            self.data_count += 1
            if self.data_count == self.total_sensors:
                self.data_collection_in_progress = False
                self.check_conditions_and_act()

        except Exception as e:
            print(f"Error occurred while processing sensor data: {e}")

    def reset_data(self):
        self.soil_moisture_values.clear()
        self.temperature = None
        self.humidity = None
        self.rain_level = None
        self.water_flow = None
        self.data_count = 0
        # Do not reset self.light_level, self.last_check_time, self.sunrise_counter, and self.is_sunrise_time

    def start_data_collection(self):
        self.reset_data()
        self.data_collection_in_progress = True
        print("A new round of data collection begins...")

    def handle_soil_moisture(self, sensor_id, value):
        self.soil_moisture_values[sensor_id] = value
        print(f"Soil moisture sensor {sensor_id}: {value:.2f}% (threshold: {self.moisture_threshold}%)")

    def handle_temperature(self, value):
        self.temperature = value
        print(f"Temperature: {value:.2f}°C (safety range: {self.temperature_threshold}°C)")

    def handle_humidity(self, value):
        self.humidity = value
        print(f"Humidity: {value:.2f}%")

    def handle_light(self, value):
        current_time = datetime.now()
        if self.light_level is None:
            self.last_check_time = current_time

        time_diff = (current_time - self.last_check_time).total_seconds() / 60
        self.last_check_time = current_time

        self.light_level = value
        print(f"Light intensity: {value:.2f} lux (threshold: {self.SUNRISE_LUX} lux)")

        if self.light_level < self.SUNRISE_LUX:
            self.sunrise_counter = max(0, self.sunrise_counter - time_diff)
        else:
            self.sunrise_counter = min(self.SUNRISE_BUFFER, self.sunrise_counter + time_diff)

        if self.sunrise_counter == 0:
            if self.is_sunrise_time:
                print("Sunrise time")
            self.is_sunrise_time = False
        elif self.sunrise_counter >= self.SUNRISE_BUFFER:
            if not self.is_sunrise_time:
                print(f"Sunrise detected, time: {current_time}")
            self.is_sunrise_time = True

        print(f"Current sunrise_counter: {self.sunrise_counter:.2f} minutes")

    def handle_rain(self, value):
        self.rain_level = value
        print(f"Rain level: {value:.2f} (detection threshold: {self.rain_detected_level})")

    def handle_water_flow(self, value):
        self.current_water_flow = value
        current_time = time.time()
        if self.irrigation_start_time is not None:
            time_diff = current_time - self.last_water_flow_time
            water_used = value * time_diff / 60  # Calculate the water consumption during this time interval
            self.irrigation_water_used += water_used
            print(f"Irrigation - Current water flow: {value:.4f} L/min, Time difference: {time_diff:.4f} seconds, Current water usage: {water_used:.4f} liters, Cumulative water usage: {self.irrigation_water_used:.4f} liters")
            self.last_water_flow_time = current_time
        print(f"Current water flow: {value:.4f} L/min")

    def start_data_collection(self):
        self.reset_data()
        self.data_collection_in_progress = True

    def check_conditions_and_act(self):
        if len(self.soil_moisture_values) < 9 or self.temperature is None or self.light_level is None or self.rain_level is None:
            print("Not all necessary sensor data has been received.")
            self.irrigation_complete.set()
            return

        average_moisture = sum(self.soil_moisture_values.values()) / len(self.soil_moisture_values)
        print(f"Average soil moisture: {average_moisture:.2f}% (threshold: {self.moisture_threshold}%)")

        should_irrigate = (
                not self.has_irrigated_today and
                0 < self.sunrise_counter < self.SUNRISE_BUFFER and  # Only irrigate in "Pre-sunrise" state
                average_moisture < self.moisture_threshold and
                self.temperature_threshold[0] <= self.temperature <= self.temperature_threshold[1] and
                self.rain_level < self.rain_detected_level and
                self.temperature > self.do_not_water_temp
        )

        if should_irrigate:
            self.irrigation_in_progress = True
            self.start_irrigation()
        else:
            reasons = []
            if self.has_irrigated_today:
                reasons.append("Irrigated today")
            if not (0 < self.sunrise_counter < self.SUNRISE_BUFFER):
                reasons.append("Not within the irrigation window before sunrise")
            if average_moisture >= self.moisture_threshold:
                reasons.append("Soil moisture is sufficient")
            if self.temperature < self.temperature_threshold[0]:
                reasons.append("Temperature is too low")
            elif self.temperature > self.temperature_threshold[1]:
                reasons.append("Temperature is too high")
            if self.rain_level >= self.rain_detected_level:
                reasons.append("Rain is detected")
            if self.temperature <= self.do_not_water_temp:
                reasons.append("Temperature is too low, not suitable for irrigation")

            if reasons:
                print(f"No irrigation. Reasons: {', '.join(reasons)}")
                self.update_led_warning(True, ', '.join(reasons))
            else:
                self.update_led_warning(False)

            self.irrigation_complete.set()

    def check_water_pump_status(self):
        try:
            catalog_url = f"{self.rest_api_base_url}/water_pump"
            response = cherrypy.lib.httputil.urlopen(catalog_url, method='GET')
            result = json.loads(response.read().decode('utf-8'))
            return result.get('water_pump_state')
        except Exception as e:
            print(f"Error checking water pump status: {e}")
            return None

    def start_irrigation(self):
        current_status = self.check_water_pump_status()
        if current_status == "ON":
            print("Water pump is already ON")
            return

        if self.irrigation_start_time is None:
            try:
                response = cherrypy.lib.httputil.urljoin(self.rest_api_base_url, "water_pump")
                result = cherrypy.lib.jsontools.json_decode(
                    cherrypy.lib.httputil.urlopen(
                        response,
                        method='POST',
                        headers=[('Content-Type', 'application/json')],
                        body=json.dumps({"command": "ON"})
                    ).read()
                )
                if result.get('status') == 'success':
                    self.irrigation_start_time = time.time()
                    self.irrigation_water_used = 0
                    self.last_water_flow_time = time.time()
                    print(f"Start irrigation. Estimated duration: {self.irrigation_duration} seconds")
                    self.update_led_warning(False)
                    self.irrigation_timer = threading.Timer(self.irrigation_duration, self.stop_irrigation)
                    self.irrigation_timer.start()
                    self.update_command_history("turn_on")  # Update command history
                else:
                    print("Failed to start the water pump.")
            except Exception as e:
                print(f"Error starting the pump: {e}")

    def stop_irrigation(self):
        current_status = self.check_water_pump_status()
        if current_status == "OFF":
            print("Water pump is already OFF")
            return

        if self.irrigation_start_time is not None:
            try:
                response = cherrypy.lib.httputil.urljoin(self.rest_api_base_url, "water_pump")
                result = cherrypy.lib.jsontools.json_decode(
                    cherrypy.lib.httputil.urlopen(
                        response,
                        method='POST',
                        headers=[('Content-Type', 'application/json')],
                        body=json.dumps({"command": "OFF"})
                    ).read()
                )
                if result.get('status') == 'success':
                    irrigation_duration = time.time() - self.irrigation_start_time
                    average_flow = self.irrigation_water_used / (
                                irrigation_duration / 60) if irrigation_duration > 0 else 0
                    total_water_used = average_flow * irrigation_duration / 60

                    print(f"Irrigation is over. Actual duration: {irrigation_duration:.2f} seconds")
                    print(f"Average water flow: {average_flow:.4f} L/min")
                    print(f"Water consumption for this irrigation: {total_water_used:.4f} liters")

                    self.total_water_used += total_water_used
                    print(f"Total water consumption: {self.total_water_used:.4f} liters")

                    self.save_water_usage()

                    self.irrigation_start_time = None
                    self.irrigation_water_used = 0
                    if self.irrigation_timer:
                        self.irrigation_timer.cancel()
                        self.irrigation_timer = None
                        self.irrigation_in_progress = False
                        self.has_irrigated_today = True
                        self.irrigation_complete.set()
                        self.update_command_history("turn_off")  # Update command history
                else:
                    print("Failed to stop the pump.")
            except Exception as e:
                print(f"Error occurred while stopping the pump: {e}")

    def update_led_warning(self, warning_on, warning_message=""):
        if warning_on != self.led_warning_state:
            self.led_warning_state = warning_on
            command_topic = "Garden/actuators/LED"
            command_msg = json.dumps(
                {"bn": "Garden/commands/", "e": [{"n": "LED", "v": 1 if warning_on else 0, "t": str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))}]})
            self.client.myPublish(command_topic, command_msg)
            print(f"LED warning{'ON' if warning_on else 'OFF'}。{warning_message if warning_on else ''}")

    def update_command_history(self, command_type):
        try:
            command = {
                "targetDeviceID": "waterpump",
                "commandType": command_type,
                "parameters": None,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            }
            response = requests.post(f"{self.catalog_url}/commands", json=command)
            if response.status_code == 200:
                print(f"Command history updated: {command_type}")
            else:
                print(f"Failed to update command history: {response.text}")
        except Exception as e:
            print(f"Error updating command history: {e}")

    def run(self):
        try:
            while True:
                current_date = datetime.now().date()
                if current_date != getattr(self, 'current_date', None):
                    self.reset_daily()
                    self.current_date = current_date

                self.start_data_collection()

                while self.data_collection_in_progress:
                    time.sleep(0.1)

                self.irrigation_complete.wait()
                self.irrigation_complete.clear()

                print(f"This loop ends. Current sunrise_counter: {self.sunrise_counter:.2f} minutes")
                print(f"Is it sunrise time: {'Yes' if self.is_sunrise_time else 'No'}")
                print(f"Has it been irrigated today: {'Yes' if self.has_irrigated_today else 'No'}")

                time.sleep(600)  # Check every 60 minutes

        except KeyboardInterrupt:
            print("Control unit shutting down...")
            if self.irrigation_timer:
                self.irrigation_timer.cancel()
            self.client.stop()

    def reset_daily(self):
        self.has_irrigated_today = False
        self.sunrise_counter = 0
        self.is_sunrise_time = False
        print("Daily reset complete. Prepare for a new day of irrigation.")

if __name__ == "__main__":
    broker = "mqtt.eclipseprojects.io"
    port = 1883
    base_url = "http://127.0.0.1:8080/garden/actuators"
    control_unit = ControlUnit(broker, port, base_url)
    control_unit.run()
