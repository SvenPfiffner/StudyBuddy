import sqlite3

class StorageService:

    def __init__(self, db_path: str):
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()