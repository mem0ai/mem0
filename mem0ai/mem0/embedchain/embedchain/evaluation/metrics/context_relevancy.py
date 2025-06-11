import concurrent.futures
import os
from string import Template
from typing import Optional

import numpy as np
import pysbd
from openai import OpenAI
from tqdm import tqdm

from embedchain.config.evaluation.base import ContextRelevanceConfig
from embedchain.evaluation.base import BaseMetric
from embedchain.utils.evaluation import EvalData, EvalMetric


class ContextRelevance(BaseMetric):
    """
    Metric for evaluating the relevance of context in a dataset.
    """

    def __init__(self, config: Optional[ContextRelevanceConfig] = ContextRelevanceConfig()):
        super().__init__(name=EvalMetric.CONTEXT_RELEVANCY.value)
        self.config = config
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key not found. Set 'OPENAI_API_KEY' or pass it in the config.")
        self.client = OpenAI(api_key=api_key)
        self._sbd = pysbd.Segmenter(language=self.config.language, clean=False)

    def _sentence_segmenter(self, text: str) -> list[str]:
        """
        Segments the given text into sentences.
        """
        return self._sbd.segment(text)

    def _compute_score(self, data: EvalData) -> float:
        """
        Computes the context relevance score for a given data item.
        """
        original_context = "\n".join(data.contexts)
        prompt = Template(self.config.prompt).substitute(context=original_context, question=data.question)
        response = self.client.chat.completions.create(
            model=self.config.model, messages=[{"role": "user", "content": prompt}]
        )
        useful_context = response.choices[0].message.content.strip()
        useful_context_sentences = self._sentence_segmenter(useful_context)
        original_context_sentences = self._sentence_segmenter(original_context)

        if not original_context_sentences:
            return 0.0
        return len(useful_context_sentences) / len(original_context_sentences)

    def evaluate(self, dataset: list[EvalData]) -> float:
        """
        Evaluates the dataset and returns the average context relevance score.
        """
        scores = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._compute_score, data) for data in dataset]
            for future in tqdm(
                concurrent.futures.as_completed(futures), total=len(dataset), desc="Evaluating Context Relevancy"
            ):
                try:
                    scores.append(future.result())
                except Exception as e:
                    print(f"Error during evaluation: {e}")

        return np.mean(scores) if scores else 0.0
