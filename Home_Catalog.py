import cherrypy
import json


class HomeCatalog:
    exposed = True

    def __init__(self, json_file):
        self.json_file = json_file
        self.load_data()

    def load_data(self):
        with open(self.json_file, 'r') as file:
            self.data = json.load(file)

    def save_data(self):
        with open(self.json_file, 'w') as file:
            json.dump(self.data, file, indent=4)

    @cherrypy.tools.json_out()
    def GET(self, *path, **params):
        if len(path) == 0:
            return "Welcome to HomeCatalog API"

        section = path[0]
        if section in self.data:
            if len(path) > 1:
                item_id = path[1]
                items = self.data[section]
                for item in items:
                    if item.get(f"{section[:-1]}ID") == item_id:
                        return item
                raise cherrypy.NotFound()
            else:
                return self.data[section]
        else:
            raise cherrypy.NotFound()

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *path, **params):
        try:
            if len(path) == 0:
                return {"error": "Invalid path"}

            section = path[0]
            if section == "commands":
                return self.add_command()
            elif section in ["actuators", "sensors"]:
                return self.add_device(section)
            else:
                return {"error": "Invalid section"}

        except Exception as e:
            cherrypy.log(f"Error in POST method: {str(e)}")
            return {"error": "An unexpected error occurred", "details": str(e)}

    def add_command(self):
        new_command = cherrypy.request.json
        new_command["commandID"] = f"cmd{len(self.data['commands']) + 1}"
        self.data['commands'].append(new_command)
        if len(self.data['commands']) > 20:
            self.data['commands'] = self.data['commands'][-20:]
        self.save_data()
        return {"message": "Command added successfully", "commandID": new_command["commandID"]}

    def add_device(self, section):
        new_item = cherrypy.request.json
        id_key = f"{section[:-1]}ID"
        if id_key not in new_item:
            return {"error": f"{id_key} is required"}

        item_id = new_item[id_key]

        if any(item.get(id_key) == item_id for item in self.data[section]):
            return {"error": f"{section.capitalize()} with {id_key} {item_id} already exists"}

        self.data[section].append(new_item)
        self.save_data()
        return {"message": f"{section.capitalize()} added successfully", id_key: item_id}

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, *path, **params):
        if len(path) < 2:
            return {"error": "Invalid path"}

        section, item_id = path[0], path[1]
        if section not in self.data:
            return {"error": "Invalid section"}

        id_key = f"{section[:-1]}ID"
        items = self.data[section]
        for index, item in enumerate(items):
            if item.get(id_key) == item_id:
                update_data = cherrypy.request.json
                if 'status' in update_data:
                    if update_data['status'] not in ['ON', 'OFF', 'active', 'inactive']:
                        return {"error": "Invalid status value"}
                items[index].update(update_data)
                self.save_data()
                return {"message": f"{section.capitalize()} updated successfully", id_key: item_id}

        return {"error": f"{section.capitalize()} with {id_key} {item_id} not found"}

    @cherrypy.tools.json_out()
    def DELETE(self, *path, **params):
        if len(path) < 2:
            return {"error": "Invalid path"}

        section, item_id = path[0], path[1]
        if section not in ["actuators", "sensors"]:
            return {"error": "Can only delete actuators or sensors"}

        id_key = f"{section[:-1]}ID"
        items = self.data[section]
        for index, item in enumerate(items):
            if item.get(id_key) == item_id:
                del items[index]
                self.save_data()
                return {"message": f"{section.capitalize()} deleted successfully", id_key: item_id}

        return {"error": f"{section.capitalize()} with {id_key} {item_id} not found"}

if __name__ == '__main__':
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    }

    cherrypy.tree.mount(HomeCatalog('catalog.json'), '/garden', conf)
    cherrypy.config.update({'server.socket_host': '127.0.0.1'})
    cherrypy.config.update({'server.socket_port': 8080})
    cherrypy.engine.start()
    cherrypy.engine.block()
