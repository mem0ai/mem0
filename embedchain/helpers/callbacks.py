import queue
from typing import Any, Union

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.schema import LLMResult

STOP_ITEM = "[END]"
"""
This is a special item that is used to signal the end of the stream.
"""


class StreamingStdOutCallbackHandlerYield(StreamingStdOutCallbackHandler):
    """
    This is a callback handler that yields the tokens as they are generated.
    For a usage example, see the :func:`generate` function below.
    """

    q: queue.Queue
    """
    The queue to write the tokens to as they are generated.
    """

    def __init__(self, q: queue.Queue) -> None:
        """
        Initialize the callback handler.
        q: The queue to write the tokens to as they are generated.
        """
        super().__init__()
        self.q = q

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Run when LLM starts running."""
        with self.q.mutex:
            self.q.queue.clear()

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        self.q.put(token)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        self.q.put(STOP_ITEM)

    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """Run when LLM errors."""
        self.q.put("%s: %s" % (type(error).__name__, str(error)))
        self.q.put(STOP_ITEM)


def generate(rq: queue.Queue):
    """
    This is a generator that yields the items in the queue until it reaches the stop item.

    Usage example:
    ```
    def askQuestion(callback_fn: StreamingStdOutCallbackHandlerYield):
        llm = OpenAI(streaming=True, callbacks=[callback_fn])
        return llm.invoke(prompt="Write a poem about a tree.")

    @app.route("/", methods=["GET"])
    def generate_output():
        q = Queue()
        callback_fn = StreamingStdOutCallbackHandlerYield(q)
        threading.Thread(target=askQuestion, args=(callback_fn,)).start()
        return Response(generate(q), mimetype="text/event-stream")
    ```
    """
    while True:
        result: str = rq.get()
        if result == STOP_ITEM or result is None:
            break
        yield result
