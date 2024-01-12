from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EvalMetric(Enum):
    CONTEXT_RELEVANCY = "context_relevancy"
    ANSWER_RELEVANCY = "answer_relevancy"
    GROUNDEDNESS = "groundedness"


class EvalData(BaseModel):
    question: str
    contexts: list[str]
    answer: str
    ground_truth: Optional[str] = None  # Not used as of now
