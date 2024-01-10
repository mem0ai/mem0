import concurrent.futures
import os
from string import Template
from typing import Optional

import numpy as np
import pysbd
from openai import OpenAI
from tqdm import tqdm

from embedchain.config.eval.base import ContextRelevanceConfig
from embedchain.eval.base import BaseMetric
from embedchain.utils.eval import EvalData

CONTEXT_RELEVANCY_PROMPT = """
Please extract relevant sentences from the provided context that is required to answer the given question.
If no relevant sentences are found, or if you believe the question cannot be answered from the given context, return the empty string ("").
While extracting candidate sentences you're not allowed to make any changes to sentences from given context or make up any sentences.
You must only provide sentences from the given context and nothing else.

Context: $context
Question: $question
"""  # noqa: E501


class ContextRelevance(BaseMetric):
    """
    Metric for context relevance.

    This class evaluates the context relevance.
    """

    def __init__(self, config: Optional[ContextRelevanceConfig] = None):
        self.config = config or ContextRelevanceConfig()
        api_key = self.config.api_key or os.environ["OPENAI_API_KEY"]
        if not api_key:
            raise ValueError("Please set the OPENAI_API_KEY environment variable or pass the `api_key` in config.")
        self.client = OpenAI(api_key=api_key)
        self._sbd = pysbd.Segmenter(language=self.config.language, clean=False)

    def _sentence_segmenter(self, text: str) -> list[str]:
        """
        Segment text into sentences.

        param: text: text to segment
        type: text: str
        return: list of sentences
        rtype: list[str]
        """
        sentences = self._sbd.segment(text)
        assert isinstance(sentences, list)
        return sentences

    def _compute_score(self, data: EvalData) -> float:
        """
        Compute the context relevance score for a single data point.
        """
        original_context = "\n".join(data.contexts)
        prompt = Template(CONTEXT_RELEVANCY_PROMPT).substitute(context=original_context, question=data.question)
        response = self.client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}",
                }
            ],
            model=self.config.model,
        )
        useful_context = response.choices[0].message.content.strip()
        useful_context_sentences = self._sentence_segmenter(useful_context)
        original_context_sentences = self._sentence_segmenter(original_context)
        return len(useful_context_sentences) / len(original_context_sentences)

    def evaluate(self, dataset: list[EvalData]):
        """
        Evaluate the dataset.

        param: dataset: dataset to evaluate
        type: dataset: list[EvalData]
        return: average context relevance score
        rtype: float
        """
        result = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_data = {executor.submit(self._compute_score, data): i for i, data in enumerate(dataset)}
            for future in tqdm(
                concurrent.futures.as_completed(future_to_data), total=len(dataset), desc="Evaluating Context Relevancy"
            ):
                i = future_to_data[future]
                try:
                    score = future.result()
                    result.append(score)
                except Exception as e:
                    print(f"Error evaluating context relevance for data point {dataset[i]}: {e}")

        return np.average(result)
