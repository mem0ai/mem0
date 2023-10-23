import json
import logging
import os

import requests


class Client:
    config_file_path = os.path.expanduser("~/.embedchain/config.json")

    def __init__(self, api_key=None, host="https://apiv2.embedchain.ai"):
        self.config_data = self.load_config()
        self.host = host

        if api_key:
            if self.check(api_key):
                self.api_key = api_key
                self.save()
            else:
                raise ValueError(
                    "Invalid API key provided. You can find your API key on https://app.embedchain.ai/settings/keys."
                )
        else:
            if "api_key" in self.config_data:
                self.api_key = self.config_data["api_key"]
                logging.info("API key loaded successfully!")
            else:
                raise ValueError(
                    "You are not logged in. Please obtain an API key from https://app.embedchain.ai/settings/keys/"
                )

    @classmethod
    def load_config(cls):
        if os.path.exists(cls.config_file_path):
            with open(cls.config_file_path, "r") as config_file:
                return json.load(config_file)
        else:
            return {}

    def save(self):
        self.config_data["api_key"] = self.api_key
        with open(self.config_file_path, "w") as config_file:
            json.dump(self.config_data, config_file, indent=4)

        logging.info("API key saved successfully!")

    def clear(self):
        if "api_key" in self.config_data:
            del self.config_data["api_key"]
            with open(self.config_file_path, "w") as config_file:
                json.dump(self.config_data, config_file, indent=4)
            self.api_key = None
            logging.info("API key deleted successfully!")
        else:
            logging.warning("API key not found in the configuration file.")

    def update(self, api_key):
        if self.check(api_key):
            self.api_key = api_key
            self.save()
            logging.info("API key updated successfully!")
        else:
            logging.warning("Invalid API key provided. API key not updated.")

    def check(self, api_key):
        validation_url = f"{self.host}/api/v1/accounts/api_keys/validate/"
        response = requests.post(validation_url, headers={"Authorization": f"Token {api_key}"})
        if response.status_code == 200:
            return True
        else:
            logging.warning(f"Response from API: {response.text}")
            logging.warning("Invalid API key. Unable to validate.")
            return False

    def get(self):
        return self.api_key

    def __str__(self):
        return self.api_key
