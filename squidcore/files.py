"""Module for handling file operations, including reading and writing files."""

# For processing specific file types
import json, yaml

# Test code
import random

# Discord
from discord.ext import commands

# Watch file changes
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from functools import wraps

class TextFile:
    """
    A class to handle text files with support for different file types and file change monitoring.
    Attributes:
        SUPPORTED_TYPES (list): A list of supported file types.
    Methods:
        __init__(path: str, file_type: str = None, exists: bool = False):
            Initializes the TextFile object with the given path and file type.
        on_edit(func):
            Decorator for watching file changes.
        read(stringify: bool = False):
            Reads the file and returns the data.
        write(data):
            Writes the data to the file.
        append(data):
            Appends the data to the file.
        __str__() -> str:
            Returns the string representation of the file content.
        __repr__() -> str:
            Returns the string representation of the TextFile object.
        __call__(*args, **kwargs):
            Calls the read method and returns the file content.
    """
    
    def __init__(self, path: str, file_type: str = None, exists: bool = False):
        self.path = path

        self.file_type = (file_type if file_type else path.split(".")[-1]).upper()
        if self.file_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type: {self.file_type}")

        if not exists:
            # Check if the file exists
            try:
                with open(self.path, "r") as f:
                    pass
            except FileNotFoundError:
                with open(self.path, "w") as f:
                    pass

    SUPPORTED_TYPES = ["TXT", "JSON", "YAML", "YML"]
    

    @classmethod
    def on_edit(cls, func):
        """Decorator for watching file changes. This funciton is currently broken."""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            class ChangeHandler(FileSystemEventHandler):
                def __init__(self, path):
                    self.path = path
                def on_modified(self, event):
                    if event.src_path == self.path:
                        func(self, *args, **kwargs)

            event_handler = ChangeHandler(self.path)
            observer = Observer()
            observer.schedule(event_handler, path=self.path, recursive=False)
            observer.start()

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
            observer.join()

        return wrapper
    
    def read(self, stringify: bool = False):
        """Reads the file and returns the data."""
        with open(self.path, "r") as f:
            if self.file_type == "TXT" or stringify:
                return f.read()
            elif self.file_type == "JSON":
                return json.load(f)
            elif self.file_type in ["YAML", "YML"]:
                return yaml.safe_load(f)

    def write(self, data):
        """Writes the data to the file."""
        with open(self.path, "w") as f:
            if self.file_type == "TXT":
                f.write(data)
            elif self.file_type == "JSON":
                json.dump(data, f, indent=4)
            elif self.file_type in ["YAML", "YML"]:
                yaml.dump(data, f, default_flow_style=False)

    def append(self, data):
        """Appends the data to the file."""
        with open(self.path, "a") as f:
            if self.file_type == "TXT":
                f.write(data)
            elif self.file_type == "JSON":
                json.dump(data, f, indent=4)
            elif self.file_type in ["YAML", "YML"]:
                f.write("\n")
                yaml.dump(data, f, default_flow_style=False)
                
    def __str__(self) -> str:
        return self.read(stringify=True)
    
    def __repr__(self) -> str:
        return f"<TextFile path={self.path}>"
    
    def __call__(self, *args, **kwargs):
        return self.read(*args, **kwargs)


# class TestClass(TextFile):
#     def __init__(self):
#         super().__init__("store/test.yaml", file_type="YAML")
#         self.file_type = "YAML"
        
#     def add_random(self):
#         # Create a random dictionary
#         add = {random.randint(0, 100): random.randint(0, 100) for _ in range(100)}
        
#         # Merge with the existing data
#         try:
#             data = self.read()
#             data.update(add)
#         except AttributeError:
#             data = add
        
#         # Write the data back
#         self.write(data)
            
#     @TextFile.on_edit
#     def on_edit(self):
#         print("File edited,", random.randint(0, 100))
#         self.add_random()
        
#     def run(self):
#         self.add_random()
#         print(self.read())
        
#         self.on_edit()
        
#         while True:
#             pass
        
# if __name__ == "__main__":
#     TestClass().run()