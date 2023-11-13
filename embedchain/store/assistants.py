import logging
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import cast

from openai import OpenAI
from openai.types.beta.threads import MessageContentText, ThreadMessage

from embedchain import Pipeline
from embedchain.config import AddConfig
from embedchain.data_formatter import DataFormatter
from embedchain.models.data_type import DataType
from embedchain.telemetry.posthog import AnonymousTelemetry
from embedchain.utils import detect_datatype

logging.basicConfig(level=logging.WARN)


class OpenAIAssistant:
    def __init__(
        self,
        name=None,
        instructions=None,
        tools=None,
        thread_id=None,
        model="gpt-4-1106-preview",
        data_sources=None,
        assistant_id=None,
        log_level=logging.WARN,
        collect_metrics=True,
    ):
        self.name = name or "OpenAI Assistant"
        self.instructions = instructions
        self.tools = tools or [{"type": "retrieval"}]
        self.model = model
        self.data_sources = data_sources or []
        self.log_level = log_level
        self._client = OpenAI()
        self._initialize_assistant(assistant_id)
        self.thread_id = thread_id or self._create_thread()
        self._telemetry_props = {"class": self.__class__.__name__}
        self.telemetry = AnonymousTelemetry(enabled=collect_metrics)
        self.telemetry.capture(event_name="init", properties=self._telemetry_props)

    def add(self, source, data_type=None):
        file_path = self._prepare_source_path(source, data_type)
        self._add_file_to_assistant(file_path)

        event_props = {
            **self._telemetry_props,
            "data_type": data_type or detect_datatype(source),
        }
        self.telemetry.capture(event_name="add", properties=event_props)
        logging.info("Data successfully added to the assistant.")

    def chat(self, message):
        self._send_message(message)
        self.telemetry.capture(event_name="chat", properties=self._telemetry_props)
        return self._get_latest_response()

    def delete_thread(self):
        self._client.beta.threads.delete(self.thread_id)
        self.thread_id = self._create_thread()

    # Internal methods
    def _initialize_assistant(self, assistant_id):
        file_ids = self._generate_file_ids(self.data_sources)
        self.assistant = (
            self._client.beta.assistants.retrieve(assistant_id)
            if assistant_id
            else self._client.beta.assistants.create(
                name=self.name, model=self.model, file_ids=file_ids, instructions=self.instructions, tools=self.tools
            )
        )

    def _create_thread(self):
        thread = self._client.beta.threads.create()
        return thread.id

    def _prepare_source_path(self, source, data_type=None):
        if Path(source).is_file():
            return source
        data_type = data_type or detect_datatype(source)
        formatter = DataFormatter(data_type=DataType(data_type), config=AddConfig(), kwargs={})
        data = formatter.loader.load_data(source)["data"]
        return self._save_temp_data(data=data[0]["content"].encode(), source=source)

    def _add_file_to_assistant(self, file_path):
        file_obj = self._client.files.create(file=open(file_path, "rb"), purpose="assistants")
        self._client.beta.assistants.files.create(assistant_id=self.assistant.id, file_id=file_obj.id)

    def _generate_file_ids(self, data_sources):
        return [
            self._add_file_to_assistant(self._prepare_source_path(ds["source"], ds.get("data_type")))
            for ds in data_sources
        ]

    def _send_message(self, message):
        self._client.beta.threads.messages.create(thread_id=self.thread_id, role="user", content=message)
        self._wait_for_completion()

    def _wait_for_completion(self):
        run = self._client.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant.id,
            instructions=self.instructions,
        )
        run_id = run.id
        run_status = run.status

        while run_status in ["queued", "in_progress", "requires_action"]:
            time.sleep(0.1)  # Sleep before making the next API call to avoid hitting rate limits
            run = self._client.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run_id)
            run_status = run.status
            if run_status == "failed":
                raise ValueError(f"Thread run failed with the following error: {run.last_error}")

    def _get_latest_response(self):
        history = self._get_history()
        return self._format_message(history[0]) if history else None

    def _get_history(self):
        messages = self._client.beta.threads.messages.list(thread_id=self.thread_id, order="desc")
        return list(messages)

    def _format_message(self, thread_message):
        thread_message = cast(ThreadMessage, thread_message)
        content = [c.text.value for c in thread_message.content if isinstance(c, MessageContentText)]
        return " ".join(content)

    def _save_temp_data(self, data, source):
        special_chars_pattern = r'[\\/:*?"<>|&=% ]+'
        sanitized_source = re.sub(special_chars_pattern, "_", source)[:256]
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, sanitized_source)
        with open(file_path, "wb") as file:
            file.write(data)
        return file_path


class AIAssistant:
    def __init__(
        self,
        name=None,
        instructions=None,
        yaml_path=None,
        assistant_id=None,
        thread_id=None,
        data_sources=None,
        log_level=logging.WARN,
        collect_metrics=True,
    ):
        logging.basicConfig(level=log_level)

        self.name = name or "AI Assistant"
        self.data_sources = data_sources or []
        self.log_level = log_level
        self.instructions = instructions
        self.assistant_id = assistant_id or str(uuid.uuid4())
        self.thread_id = thread_id or str(uuid.uuid4())
        self.pipeline = Pipeline.from_config(yaml_path=yaml_path) if yaml_path else Pipeline()
        self.pipeline.local_id = self.pipeline.config.id = self.thread_id

        if self.instructions:
            self.pipeline.system_prompt = self.instructions

        print(
            f"🎉 Created AI Assistant with name: {self.name}, assistant_id: {self.assistant_id}, thread_id: {self.thread_id}"  # noqa: E501
        )

        # telemetry related properties
        self._telemetry_props = {"class": self.__class__.__name__}
        self.telemetry = AnonymousTelemetry(enabled=collect_metrics)
        self.telemetry.capture(event_name="init", properties=self._telemetry_props)

        if self.data_sources:
            for data_source in self.data_sources:
                metadata = {"assistant_id": self.assistant_id, "thread_id": "global_knowledge"}
                self.pipeline.add(data_source["source"], data_source.get("data_type"), metadata=metadata)

    def add(self, source, data_type=None):
        metadata = {"assistant_id": self.assistant_id, "thread_id": self.thread_id}
        self.pipeline.add(source, data_type=data_type, metadata=metadata)
        event_props = {
            **self._telemetry_props,
            "data_type": data_type or detect_datatype(source),
        }
        self.telemetry.capture(event_name="add", properties=event_props)

    def chat(self, query):
        where = {
            "$and": [
                {"assistant_id": {"$eq": self.assistant_id}},
                {"thread_id": {"$in": [self.thread_id, "global_knowledge"]}},
            ]
        }
        return self.pipeline.chat(query, where=where)

    def delete(self):
        self.pipeline.reset()
