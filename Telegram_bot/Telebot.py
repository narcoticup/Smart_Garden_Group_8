import telepot
import time
import datetime
import threading
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
from MyMQTT import MyMQTT
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class IcscBot:
    def __init__(self, token, clientID, broker, port, topics, home_catalog_url, thingspeak_config):
        self.token = token
        self.bot = telepot.Bot(self.token)
        self.callback_dict = {
            'chat': self.on_chat_message,
            'callback_query': self.queries
        }

        self.topics = topics
        self.home_catalog_url = home_catalog_url
        self.thingspeak_config = thingspeak_config
        self.irrigation_timer = None
        self.last_chat_id = None

        # Create MyMQTT instance
        self.client_mqtt = MyMQTT(clientID, broker, port, self)

    def start(self):
        MessageLoop(self.bot, self.callback_dict).run_as_thread()
        self.client_mqtt.start()
        self.client_mqtt.mySubscribe(self.topics["LED"])
        logging.info(f"Subscribed to {self.topics['LED']}")

    def on_chat_message(self, msg):
        content_type, chat_type, chat_ID = telepot.glance(msg)
        self.last_chat_id = chat_ID  # Update the chat_ID of the last user who interacted with the bot
        cmd = msg['text']

        if cmd == '/start':
            self.bot.sendMessage(chat_ID, "Welcome to the Smart Garden System! Use /help to see available commands.")
        elif cmd == '/help':
            help_text = """
            Available commands:
            /start - Welcome message
            /help - Show this help message
            /status - Get current status of all devices
            /sensor_data - Get the latest sensor data
            /control_pump_on - Turn on the water pump for 10 minutes
            /control_pump_off - Turn off the water pump
            """
            self.bot.sendMessage(chat_ID, help_text)
        elif cmd == '/status':
            status = self.get_device_status()
            self.bot.sendMessage(chat_ID, status)
        elif cmd == '/sensor_data':
            sensor_data = self.get_sensor_data()
            self.bot.sendMessage(chat_ID, sensor_data)
        elif cmd == '/control_pump_on':
            response = self.control_pump('turn_on', chat_ID)
            self.bot.sendMessage(chat_ID, response)
        elif cmd == '/control_pump_off':
            response = self.control_pump('turn_off', chat_ID)
            self.bot.sendMessage(chat_ID, response)
        else:
            self.bot.sendMessage(chat_ID, "Unknown command. Use /help to see available commands.")

    def queries(self, msg):
        query_id, ch_id, query = telepot.glance(msg, flavor='callback_query')
        # Handle any callback queries (if needed)

    def get_device_status(self):
        try:
            response = requests.get(f"{self.home_catalog_url}/garden/actuators")
            if response.status_code == 200:
                actuators = response.json()
                logging.debug(f"Raw actuator data: {actuators}")
                status_text = "Current Device Status:\n"
                for actuator in actuators:
                    status_text += f"{actuator['actuatorName']}: {actuator['status']}\n"
                return status_text
            else:
                logging.error(f"Failed to get device status. Status code: {response.status_code}")
                return "Failed to get device status."
        except requests.RequestException as e:
            logging.error(f"Error getting device status: {str(e)}")
            return f"Error getting device status: {str(e)}"

    def get_sensor_data(self):
        try:
            url = f"https://api.thingspeak.com/channels/{self.thingspeak_config['channelID']}/feeds.json"
            params = {
                'api_key': self.thingspeak_config['apiKey'],
                'results': 1
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                latest_entry = data['feeds'][0]
                sensor_text = "Latest Sensor Data:\n"

                # 使用新的字段名称
                field_names = {
                    'field1': 'Humidity',
                    'field2': 'Light',
                    'field3': 'Temperature',
                    'field4': 'Soil Moisture',
                    'field5': 'Rain',
                    'field6': 'Water Flow'
                }

                units = {
                    'Humidity': '%',
                    'Light': 'lux',
                    'Temperature': '°C',
                    'Soil Moisture': '%',
                    'Rain': 'mm',
                    'Water Flow': 'L/min'
                }

                for field, value in latest_entry.items():
                    if field.startswith('field') and field in field_names:
                        name = field_names[field]
                        unit = units.get(name, '')
                        sensor_text += f"{name}: {value} {unit}\n"

                return sensor_text
            else:
                logging.error(f"Failed to get sensor data. Status code: {response.status_code}")
                return "Failed to get sensor data."
        except requests.RequestException as e:
            logging.error(f"Error getting sensor data: {str(e)}")
            return f"Error getting sensor data: {str(e)}"

    def control_pump(self, action, chat_ID):
        try:
            pump_id = "waterpump"
            payload = {
                "commandType": action,
                "parameters": {"duration": 600} if action == "turn_on" else None
            }
            response = requests.post(f"{self.home_catalog_url}/garden/actuators/{pump_id}", json=payload)
            response.raise_for_status()

            if response.status_code == 200:
                self.update_command_history(pump_id, action)

                status_payload = {"status": "ON" if action == "turn_on" else "OFF"}
                status_response = requests.put(f"{self.home_catalog_url}/garden/actuators/{pump_id}/status",
                                               json=status_payload)
                status_response.raise_for_status()
                logging.info(f"Updated pump status in catalog: {status_payload}")

                message = f"Water pump {action.replace('turn_', '').replace('on', 'ON').replace('off', 'OFF')} command sent successfully."

                if action == "turn_on":
                    self.last_chat_id = chat_ID
                    if self.irrigation_timer:
                        self.irrigation_timer.cancel()
                    self.irrigation_timer = threading.Timer(600, self.auto_turn_off_pump)
                    self.irrigation_timer.start()
                    message += " The pump will automatically turn off after 10 minutes."
                elif action == "turn_off" and self.irrigation_timer:
                    self.irrigation_timer.cancel()
                    self.irrigation_timer = None

                for i in range(5):
                    time.sleep(1)
                    current_status = self.get_device_status()
                    logging.debug(f"Attempt {i + 1}: Current status after command: {current_status}")
                    if ("Water Pump: ON" in current_status and action == "turn_on") or \
                            ("Water Pump: OFF" in current_status and action == "turn_off"):
                        logging.info("Pump status successfully updated and confirmed.")
                        break
                else:
                    message += " However, the status may not have updated immediately. Please check again later."
                    logging.warning("Pump status not confirmed after 5 attempts.")
            else:
                message = f"Failed to {action.replace('turn_', '').replace('on', 'turn on').replace('off', 'turn off')} the water pump. Server response: {response.text}"
                logging.error(f"Failed to control pump. Server response: {response.text}")

            return message

        except requests.RequestException as e:
            logging.error(f"RequestException in control_pump: {str(e)}")
            return f"Error controlling water pump: {str(e)}"
        except Exception as e:
            logging.error(f"Unexpected error in control_pump: {str(e)}")
            return f"An unexpected error occurred: {str(e)}"

    def auto_turn_off_pump(self):
        logging.info("Auto turning off pump after 10 minutes")
        response = self.control_pump('turn_off', self.last_chat_id)
        if self.last_chat_id:
            self.bot.sendMessage(self.last_chat_id,
                                 "Irrigation completed. The water pump has been automatically turned off.")
        self.irrigation_timer = None

    def update_command_history(self, device_id, command_type):
        try:
            command = {
                "targetDeviceID": device_id,
                "commandType": command_type,
                "parameters": {"duration": 600} if command_type == "turn_on" else None,
                "status": "completed",
                "timestamp": datetime.datetime.now().isoformat()
            }
            response = requests.post(f"{self.home_catalog_url}/garden/commands", json=command)
            if response.status_code == 200:
                logging.info(f"Command history updated: {command_type}")
            else:
                logging.error(f"Failed to update command history. Status code: {response.status_code}")
        except requests.RequestException as e:
            logging.error(f"Error updating command history: {str(e)}")

    def notify(self, topic, payload):
        logging.debug(f"Received MQTT message on topic {topic}: {payload}")
        if topic == self.topics["LED"]:
            try:
                # First, decode the bytes to string if necessary
                if isinstance(payload, bytes):
                    payload = payload.decode('utf-8')

                # Then, parse the JSON string
                msg = json.loads(payload)

                # If the message is still a string, parse it again
                if isinstance(msg, str):
                    msg = json.loads(msg)

                led_state = msg["e"][0]["v"]
                timestamp = msg["e"][0]["t"]

                if led_state == 1:
                    alert_message = f"🚨 ALERT: LED Warning Activated! 🚨\n"
                    alert_message += f"Time: {timestamp}\n"
                    alert_message += "The garden system has detected conditions that require attention."
                else:
                    alert_message = f"✅ NOTICE: LED Warning Deactivated\n"
                    alert_message += f"Time: {timestamp}\n"
                    alert_message += "The garden conditions have returned to normal."

                logging.info(alert_message)

                # Send alert to Telegram
                if self.last_chat_id:
                    self.bot.sendMessage(self.last_chat_id, alert_message)
                    logging.info(f"Alert message sent to Telegram user {self.last_chat_id}")
                else:
                    logging.warning("No available chat_ID to send Telegram message")
            except json.JSONDecodeError as e:
                logging.error(f"Unable to parse MQTT message: {payload}. Error: {str(e)}")
            except KeyError as e:
                logging.error(f"Incorrect MQTT message format: {payload}. Missing key: {str(e)}")
            except Exception as e:
                logging.error(f"Error processing MQTT message: {str(e)}")
                logging.error(f"Payload: {payload}")


if __name__ == "__main__":
    token = '7309080234:AAEGmUtPP_hTJOy5dCrwn76OS7NRdP3c7Fg'
    clientID = 'Oreo1012'
    broker = 'mqtt.eclipseprojects.io'
    port = 1883
    topics = {
        "sensorData": "Garden/sensors",
        "actuatorCommands": "Garden/actuators",
        "LED": "Garden/actuators/LED"
    }
    home_catalog_url = 'http://127.0.0.1:8080'  # Assuming Home Catalog runs on localhost
    thingspeak_config = {
        "apiKey": "JF91IDPD4OPIIYT4",
        "channelID": "2576980",
        "username": "DjgfMx01ABEZJxwlMQIACxQ",
        "clientId": "DjgfMx01ABEZJxwlMQIACxQ",
        "password": "dOD7/m73t0PnYVYQjuWLZObs"
    }

    bot = IcscBot(token, clientID, broker, port, topics, home_catalog_url, thingspeak_config)
    bot.start()

    logging.info("Bot started. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    finally:
        bot.client_mqtt.stop()
        logging.info("MQTT client stopped.")