import json
import cherrypy
from Device_Connector_act import DeviceConnectorAct


class DCInstancerAct:
    def __init__(self, config_file):
        """
        Initialize the DCInstancerAct class, load the configuration file and initialize the actuator connector.
        """
        self.config = self.load_config(config_file)
        self.clientID = self.config['clientID']
        self.base_topic = self.config['baseTopic']
        self.devicesList = self.config['devicesList']
        self.broker = self.config['broker']
        self.port = self.config['port']

    def load_config(self, file_path):
        """
        Load configuration from a JSON file.
        """
        with open(file_path, 'r') as file:
            return json.load(file)

    def start(self):
        """
       Start the actuator connector and the REST service.
        """
        self.device_connector_act = DeviceConnectorAct(
            clientID=self.clientID,
            broker=self.broker,
            port=self.port,
            base_topic=self.base_topic,
            devicesList=self.devicesList
        )


        cherrypy_config = {
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'tools.sessions.on': True,
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'application/json')],
            }
        }

        cherrypy.tree.mount(self.device_connector_act, '/garden/actuators', cherrypy_config)
        cherrypy.server.socket_host = '127.0.0.1'
        cherrypy.server.socket_port = 8080
        cherrypy.engine.start()
        print("REST service started...")
        cherrypy.engine.block()

    def stop(self):
        """
        Stop the actuator connector and the REST service.
        """
        if hasattr(self, 'device_connector_act'):
            self.device_connector_act.stop()
        cherrypy.engine.exit()



if __name__ == '__main__':
    config_file = 'setting_act.json'
    instancer = DCInstancerAct(config_file)
    instancer.start()
