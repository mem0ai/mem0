import os
from string import Template
from typing import Optional

import numpy as np
from openai import OpenAI

from ..base import BaseMetric
from ..config import EvalConfig
from ..utils import EvalData

CONTEXT_RELEVANCY_PROMPT = Template(
    """
                            Please extract relevant sentences from the provided context that is required to answer the given question.
                            If no relevant sentences are found, or if you believe the question cannot be answered from the given context, return the empty string ("").
                            While extracting candidate sentences you're not allowed to make any changes to sentences from given context or make up any sentences.
                            You must only provide sentences from the given context and nothing else.
                            
                            Context: $context
                            Question: $question
                            """  # noqa: E501
)


class ContextRelevance(BaseMetric):
    """
    Metric for context relevance.

    This evaluator evaluates the context relevance of a model.
    """

    def __init__(self, config: Optional[EvalConfig] = None):
        super().__init__()
        self.config = config or EvalConfig()
        api_key = self.config.api_key or os.environ["OPENAI_API_KEY"]
        if not api_key:
            raise ValueError("Please set the OPENAI_API_KEY environment variable or pass the `api_key` in config.")
        self.client = OpenAI(api_key=api_key)

    def _compute_score(self, data: EvalData) -> float:
        """
        Compute the context relevance score for a single data point.
        """
        original_context = "\n".join(data.contexts)
        prompt = CONTEXT_RELEVANCY_PROMPT.substitute(context=original_context, question=data.question)
        response = self.client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}",
                }
            ],
            model=self.config.model_name,
        )
        useful_context = response.choices[0].message.content
        return len(useful_context) / len(original_context)

    def evaluate_data(self, dataset: list[EvalData]):
        """
        Evaluate the dataset.

        param: dataset: dataset to evaluate
        type: dataset: list[EvalData]
        return: average context relevance score
        rtype: float
        """
        result = []
        for data in dataset:
            score = self._compute_score(data)
            result.append(score)
        return np.average(result)
