import os
import threading
import importlib
import json

base_notion_config = {
    "Notion-API-Key": None,
    "parent-page-id": None
}

nullable_keys = []

stop_event = threading.Event()

ignored_automatons = [
    #"Canvas",
    #"Google_Classroom"
]

class Config:
    def __init__(self, filename="config.json"):
        
        self.filename = filename
        self.lock = threading.Lock()
        
        try:
            with open(filename, "r") as f:
                self._data = json.loads(f.read())
        except Exception as e:
            print(e)
            self._data = {}

    def get_data(self):
        return self._data
        
    def write_data(self):
        with open(self.filename, "w") as f:
            f.write(json.dumps(self._data, indent=2))

def check_config(config):
    with config.lock:
        data = config.get_data()
        if "Notion" not in data:
            data["Notion"] = base_notion_config
            config.write_data()

        for key in base_notion_config.keys():
            if key not in data["Notion"]:
                data["Notion"][key] = base_notion_config[key]
                config.write_data()

        for key, value in data["Notion"].items():
            if value is None and key not in nullable_keys:
                config.write_data()
                raise Exception("Notion Configuration is Incomplete")

def main():
    threads = []
    config = Config()
    check_config(config)
    
    for integration in os.listdir():
        dirpath = os.path.join(".", integration)
        if not os.path.isdir(dirpath) or not os.path.exists(os.path.join(dirpath, "main.py")) or integration in ignored_automatons:
            continue
        
        filename = os.path.join(dirpath, "main.py")[2:]
        module_name = filename.replace(".py", "").replace("/", ".").replace("\\", ".")
        module = importlib.import_module(module_name)
        threads.append(threading.Thread(target=module.main, args=(stop_event, config)))

    try:
        
        for thread in threads:
            thread.start()
            
        for thread in threads:
            thread.join()
            
    except (KeyboardInterrupt, Exception) as e:
        stop_event.set()
            
        for thread in threads:
            thread.join()


if __name__ == "__main__":
    main()