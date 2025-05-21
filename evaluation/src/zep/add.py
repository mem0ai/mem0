import argparse
import json
import os

from dotenv import load_dotenv
from tqdm import tqdm
from zep_cloud import Message
from zep_cloud.client import Zep

load_dotenv()


class ZepAdd:
    def __init__(self, data_path=None):
        self.zep_client = Zep(api_key=os.getenv("ZEP_API_KEY"))
        self.data_path = data_path
        self.data = None
        if data_path:
            self.load_data()

    def load_data(self):
        with open(self.data_path, "r") as f:
            self.data = json.load(f)
        return self.data

    def process_conversation(self, run_id, item, idx):
        conversation = item["conversation"]

        user_id = f"run_id_{run_id}_experiment_user_{idx}"
        session_id = f"run_id_{run_id}_experiment_session_{idx}"

        # # delete all memories for the two users
        # self.zep_client.user.delete(user_id=user_id)
        # self.zep_client.memory.delete(session_id=session_id)

        self.zep_client.user.add(user_id=user_id)
        self.zep_client.memory.add_session(
            user_id=user_id,
            session_id=session_id,
        )

        print("Starting to add memories... for user", user_id)
        for key in tqdm(conversation.keys(), desc=f"Processing user {user_id}"):
            if key in ["speaker_a", "speaker_b"] or "date" in key:
                continue

            date_time_key = key + "_date_time"
            timestamp = conversation[date_time_key]
            chats = conversation[key]

            for chat in tqdm(chats, desc=f"Adding chats for {key}", leave=False):
                self.zep_client.memory.add(
                    session_id=session_id,
                    messages=[
                        Message(
                            role=chat["speaker"],
                            role_type="user",
                            content=f"{timestamp}: {chat['text']}",
                        )
                    ],
                )

    def process_all_conversations(self, run_id):
        if not self.data:
            raise ValueError("No data loaded. Please set data_path and call load_data() first.")
        for idx, item in tqdm(enumerate(self.data)):
            if idx == 0:
                self.process_conversation(run_id, item, idx)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", type=str, required=True)
    args = parser.parse_args()
    zep_add = ZepAdd(data_path="../../dataset/locomo10.json")
    zep_add.process_all_conversations(args.run_id)
