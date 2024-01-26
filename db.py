import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import ssl

class NoSQLDatabaseConnector:
    def __init__(self, uri):
        try:
            # Create a secure SSL context
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # Disable older versions of TLS

            # Use secure context in MongoClient
            self.client = MongoClient(uri, ssl=True, ssl_cert_reqs=ssl.CERT_REQUIRED, ssl_context=ssl_context)
            self.db = self.client['your_database_name']  # replace with your database name
        except ConnectionFailure:
            print("Failed to connect to server.")

    def create_record(self, collection_name, record):
        collection = self.db[collection_name]
        return collection.insert_one(record).inserted_id

    def read_record(self, collection_name, query):
        collection = self.db[collection_name]
        return collection.find_one(query)

    def read_all_records(self, collection_name, query={}):
        collection = self.db[collection_name]
        return list(collection.find(query))

    def update_record(self, collection_name, query, new_values):
        collection = self.db[collection_name]
        return collection.update_one(query, {'$set': new_values})

    def delete_record(self, collection_name, query):
        collection = self.db[collection_name]
        return collection.delete_one(query)

# Usage
if __name__ == "__main__":
    uri = "your_mongodb_uri"  # Replace with your MongoDB URI
    db_connector = NoSQLDatabaseConnector(uri)

    # Example operations
    inserted_id = db_connector.create_record("collection_name", {"key": "value"})
    read_result = db_connector.read_record("collection_name", {"key": "value"})
    all_records = db_connector.read_all_records("collection_name")
    db_connector.update_record("collection_name", {"key": "value"}, {"new_key": "new_value"})
    db_connector.delete_record("collection_name", {"key": "value"})
