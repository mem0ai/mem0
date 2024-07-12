import concurrent.futures
import logging
import os
from string import Template
from typing import Optional

import numpy as np
from openai import OpenAI
from tqdm import tqdm

from embedchain.config.evaluation.base import AnswerRelevanceConfig
from embedchain.evaluation.base import BaseMetric
from embedchain.utils.evaluation import EvalData, EvalMetric

logger = logging.getLogger(__name__)


class AnswerRelevance(BaseMetric):
    """
    Metric for evaluating the relevance of answers.
    """

    def __init__(self, config: Optional[AnswerRelevanceConfig] = AnswerRelevanceConfig()):
        super().__init__(name=EvalMetric.ANSWER_RELEVANCY.value)
        self.config = config
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key not found. Set 'OPENAI_API_KEY' or pass it in the config.")
        self.client = OpenAI(api_key=api_key)

    def _generate_prompt(self, data: EvalData) -> str:
        """
        Generates a prompt based on the provided data.
        """
        return Template(self.config.prompt).substitute(
            num_gen_questions=self.config.num_gen_questions, answer=data.answer
        )

    def _generate_questions(self, prompt: str) -> list[str]:
        """
        Generates questions from the prompt.
        """
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip().split("\n")

    def _generate_embedding(self, question: str) -> np.ndarray:
        """
        Generates the embedding for a question.
        """
        response = self.client.embeddings.create(
            input=question,
            model=self.config.embedder,
        )
        return np.array(response.data[0].embedding)

    def _compute_similarity(self, original: np.ndarray, generated: np.ndarray) -> float:
        """
        Computes the cosine similarity between two embeddings.
        """
        original = original.reshape(1, -1)
        norm = np.linalg.norm(original) * np.linalg.norm(generated, axis=1)
        return np.dot(generated, original.T).flatten() / norm

    def _compute_score(self, data: EvalData) -> float:
        """
        Computes the relevance score for a given data item.
        """
        prompt = self._generate_prompt(data)
        generated_questions = self._generate_questions(prompt)
        original_embedding = self._generate_embedding(data.question)
        generated_embeddings = np.array([self._generate_embedding(q) for q in generated_questions])
        similarities = self._compute_similarity(original_embedding, generated_embeddings)
        return np.mean(similarities)

    def evaluate(self, dataset: list[EvalData]) -> float:
        """
        Evaluates the dataset and returns the average answer relevance score.
        """
        results = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_data = {executor.submit(self._compute_score, data): data for data in dataset}
            for future in tqdm(
                concurrent.futures.as_completed(future_to_data), total=len(dataset), desc="Evaluating Answer Relevancy"
            ):
                data = future_to_data[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"Error evaluating answer relevancy for {data}: {e}")

        return np.mean(results) if results else 0.0
