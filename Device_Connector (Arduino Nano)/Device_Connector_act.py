import json
import time
import os
import cherrypy
from MyMQTT import MyMQTT
from Sensors import LED, WaterPump

class DeviceConnectorAct:
    exposed = True

    def __init__(self, clientID, broker, port, base_topic, devicesList, catalog_path):
        """
        Initialize the DeviceConnectorAct class to set up the MQTT connection and initialize the device.
        """
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.base_topic = base_topic
        self.devicesList = devicesList
        self.catalog_path = catalog_path

        # Initialize the MQTT client
        self.mqtt_client = MyMQTT(self.clientID, self.broker, self.port, self)
        self.mqtt_client.start()

        # Initialize the executor
        self.led = LED(device_id=self.get_device_id("led"), topic=self.get_topic("led"))
        self.waterpump = WaterPump(device_id=self.get_device_id("waterpump"), url=self.get_url("waterpump"), topic=self.get_topic("waterpump"))

        # Initialization state
        self.led_state = "OFF"
        self.waterpump_state = "OFF"

        # Subscribe to topic
        self.mqtt_client.mySubscribe(f"{self.base_topic}/#")

    def update_catalog(self, device_id, status):
        """
       Updates the status of the device in the catalog.json file.
        """
        with open(self.catalog_path, 'r') as file:
            catalog = json.load(file)

        for device in catalog['actuators']:
            if device['actuatorID'] == device_id:
                device['status'] = status
                break

        with open(self.catalog_path, 'w') as file:
            json.dump(catalog, file, indent=4)

    def get_device_id(self, device_name):
        """
        Get the device ID from the configuration file based on the device name.
        """
        for device in self.devicesList:
            if device['deviceID'] == device_name:
                return device['deviceID']
        raise ValueError(f"设备 {device_name} 未找到")

    def get_url(self, device_name):
        """
        Get the REST URL from the configuration file based on the device name.
        """
        for device in self.devicesList:
            if device['deviceID'] == device_name:
                for service in device['servicesDetails']:
                    if service['serviceType'] == 'REST':
                        return service['url']
        raise ValueError(f"设备 {device_name} 的 REST URL 未找到")

    def get_topic(self, device_name):
        """
        Get the MQTT topic from the configuration file based on the device name.
        """
        for device in self.devicesList:
            if device['deviceID'] == device_name:
                for service in device['servicesDetails']:
                    if service['serviceType'] == 'MQTT':
                        return service['topic']
        raise ValueError(f"MQTT topic for device {device_name} not found")

    def start(self):
        print("Start listening for MQTT messages...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.mqtt_client.stop()

    def notify(self, topic, msg):
        """
        Process received MQTT messages.
        """
        print(f"Received message: {msg} from topic: {topic}")
        try:
            message = json.loads(msg)
        except json.JSONDecodeError:
            print("The message format is incorrect and cannot be parsed.")
            return

        if "LED" in topic:
            self.handle_led(message)
        elif "waterpump" in topic:
            self.handle_waterpump(message)

    def handle_led(self, message):
        """
        Control the LED state based on the received message.
        """
        try:
            command = message.get('command', None)
            if command:
                self.control_led(command)
            elif "e" in message:
                event = message['e'][0]
                command = 'ON' if event['v'] == 1 else 'OFF'
                if self.led_state != command:
                    self.control_led(command)
        except KeyError as e:
            print(f"Error")

    def control_led(self, command):
        """
        Methods to control LED status. Can be called via REST API.
        """
        if self.led_state != command:
            self.led.set_state(command == "ON")
            self.led_state = command
            self.publish_led_state(command)
        else:
            print(f"LED is already in {command} state")

    def publish_led_state(self, command):
        """
        Publish the current state of the LED to MQTT.
        """
        mqtt_message = {
            "bn": f"{self.base_topic}/LED",
            "e": [
                {
                    "n": "led",
                    "v": 1 if command == "ON" else 0,
                    "u": "binary",
                    "t": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                }
            ]
        }
        self.mqtt_client.myPublish(f"{self.base_topic}/LED", mqtt_message)
        print('published')

    def handle_waterpump(self, message):
        """
        Control the pump status according to the received message.
        """
        try:
            command = "ON" if message['e'][0]['v'] == 1 else "OFF"
            if command == self.waterpump_state:
                return
            self.control_waterpump(command)
        except KeyError as e:
            print(f"缺少预期的键: {e}")

    def control_waterpump(self, command):
        """
        Method to control the pump status. Can be called through REST API.
        """
        if self.waterpump_state != command:
            self.waterpump.set_state(command == "ON")
            self.waterpump_state = command
            self.update_catalog('waterpump', command)

            # Build and publish an MQTT message to update other subscribers
            mqtt_message = {
                "bn": f"{self.base_topic}/commands/waterpump",
                "e": [
                    {
                        "n": "waterpump",
                        "v": 1 if command == "ON" else 0,
                        "u": "binary",
                        "t": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                    }
                ]
            }
            self.mqtt_client.myPublish(f"{self.base_topic}/commands/waterpump", mqtt_message)
            print(f"Publishing MQTT message: {mqtt_message}")
            return {"status": "success", "message": f"Water pump turned {command}"}
        else:
            print(f"Water pump is already {command}")
            return {"status": "error", "message": f"Water pump is already {command}"}

    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        """
        Get the current status of the pump.
        """
        if len(uri) != 0 and uri[0] == "waterpump":
            return {"status": "success", "waterpump_state": self.waterpump_state}
        else:
            return {"status": "error", "message": "Invalid URL"}

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *uri, **params):
        """
        Change the pump status.
        """
        if len(uri) != 0 and uri[0] == "waterpump":
            input_json = cherrypy.request.json
            command = input_json.get("command", "OFF")
            return self.control_waterpump(command)
        else:
            return {"status": "error", "message": "Invalid URL"}


if __name__ == '__main__':
    cherrypy_config = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    }

    config_file = 'setting_act.json'
    catalog_path = r"E:\06- PoliTo\03-Semester 3\03- IoT and Cloud\03-Project\Code\Smart Garden\catalog.json"
    with open(config_file, 'r') as file:
        config = json.load(file)

    device_connector_act = DeviceConnectorAct(
        clientID=config['clientID'],
        broker=config['broker'],
        port=config['port'],
        base_topic=config['baseTopic'],
        devicesList=config['devicesList'],
        catalog_path=catalog_path)

    cherrypy.tree.mount(device_connector_act, '/garden/actuators', cherrypy_config)
    cherrypy.server.socket_host = '127.0.0.1'
    cherrypy.server.socket_port = 8080
    cherrypy.engine.start()
    cherrypy.engine.block()
