from Device_Connector import DeviceConnector


class DCInstancer:
    def __init__(self, config_file):
        self.config_file = config_file
        self.device_connector = None

    def start(self):
        self.device_connector = DeviceConnector(self.config_file)
        self.device_connector.run()

    def stop(self):
        if self.device_connector:
            self.device_connector.stop()


if __name__ == '__main__':
    config_file_path = 'setting_sen.json'
    instancer = DCInstancer(config_file_path)

    try:
        instancer.start()
    except KeyboardInterrupt:
        instancer.stop()
