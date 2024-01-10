import os
from string import Template
from typing import Optional

import numpy as np
import pysbd
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
        self.sbd = pysbd.Segmenter(language=self.config.language, clean=False)

    def _sentence_segmenter(self, text: str) -> list[str]:
        """
        Segment text into sentences.

        param: text: text to segment
        type: text: str
        return: list of sentences
        rtype: list[str]
        """
        sentences = self.sbd.segment(text)
        assert isinstance(sentences, list)
        return sentences

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
        useful_context = response.choices[0].message.content.strip()
        useful_context_sentences = self._sentence_segmenter(useful_context)
        original_context_sentences = self._sentence_segmenter(original_context)
        return len(useful_context_sentences) / len(original_context_sentences)

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
