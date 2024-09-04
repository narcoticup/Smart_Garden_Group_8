from Control_unit import ControlUnit

class ControlUnitInstancer:
    def __init__(self):
        self.config = {
            "broker": "mqtt.eclipseprojects.io",
            "port": 1883,
            "baseUrl": "http://127.0.0.1:8080/garden/actuators"
        }
        self.control_unit = None

    def start(self):
        self.control_unit = ControlUnit(
            broker=self.config['broker'],
            port=self.config['port'],
            base_url=self.config['baseUrl']
        )
        self.control_unit.run()

    def stop(self):
        if self.control_unit:
            self.control_unit.stop()

if __name__ == '__main__':
    instancer = ControlUnitInstancer()

    try:
        instancer.start()
    except KeyboardInterrupt:
        instancer.stop()
