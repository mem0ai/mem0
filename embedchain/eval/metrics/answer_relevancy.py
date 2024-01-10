import concurrent.futures
import logging
import os
from string import Template
from typing import Optional

import numpy as np
from openai import OpenAI
from tqdm import tqdm

from embedchain.config.eval.base import AnswerRelevanceConfig
from embedchain.eval.base import BaseMetric
from embedchain.utils.eval import EvalData

ANSWER_RELEVANCY_PROMPT = """
Please provide $num_gen_questions questions from the provided answer.
You must provide the complete question, if are not able to provide the complete question, return empty string ("").
Please only provide one question per line without numbers or bullets to distinguish them.
You must only provide the questions and no other text.

$answer
"""


class AnswerRelevance(BaseMetric):
    """
    Metric for answer relevance.

    This class evaluates the answer relevance.
    """

    def __init__(self, config: Optional[AnswerRelevanceConfig] = None):
        self.config = config or AnswerRelevanceConfig()
        api_key = self.config.api_key or os.environ["OPENAI_API_KEY"]
        if not api_key:
            raise ValueError("Please set the OPENAI_API_KEY environment variable or pass the `api_key` in config.")
        self.client = OpenAI(api_key=api_key)

    def _generate_prompt(self, data: EvalData) -> str:
        """
        Generate the prompt for the given data.
        """
        prompt = Template(ANSWER_RELEVANCY_PROMPT).substitute(
            num_gen_questions=self.config.num_gen_questions, answer=data.answer
        )
        return prompt

    def _generate_questions(self, prompt: str) -> list[str]:
        """
        Generate questions from the given prompt.
        """
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": f"{prompt}"}],
        )
        result = response.choices[0].message.content.strip()
        generated_questions = [result.split("\n")]
        return generated_questions

    def _generate_embedding(self, question: str) -> list[float]:
        """
        Generate the embedding for the given question.
        """
        result = self.client.embeddings.create(
            input=question,
            model=self.config.embedder,
        )
        return result.data[0].embedding

    def _compute_similarity(
        self, original_question_embeddings: list[float], generated_question_embeddings: list[list[float]]
    ) -> float:
        """
        Compute the cosine similarity between original and a generated question.
        """
        og_question_vec = np.asarray(original_question_embeddings).reshape(1, -1)
        gen_question_vec = np.asarray(generated_question_embeddings)
        norm = np.linalg.norm(og_question_vec, axis=1) * np.linalg.norm(gen_question_vec, axis=1)
        return np.dot(gen_question_vec, og_question_vec.T).reshape(-1) / norm

    def _compute_score(self, data: EvalData) -> float:
        """
        Compute answer relevancy score.
        """
        prompt = self._generate_prompt(data)
        generated_questions = self._generate_questions(prompt)
        generated_question_embeddings = [self._generate_embedding(question) for question in generated_questions]
        original_question_embedding = self._generate_embedding(data.question)
        cosine_similarities = self._compute_similarity(original_question_embedding, generated_question_embeddings)
        score = cosine_similarities.mean()
        return score

    def evaluate(self, dataset: list[EvalData]):
        """
        Evaluate the dataset.

        param: dataset: dataset to evaluate
        type: dataset: list[EvalData]
        return: average answer relevance score
        rtype: float
        """
        result = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_data = {executor.submit(self._compute_score, data): i for i, data in enumerate(dataset)}
            for future in tqdm(
                concurrent.futures.as_completed(future_to_data),
                total=len(future_to_data),
                desc="Evaluating Answer Relevancy",
            ):
                i = future_to_data[future]
                try:
                    score = future.result()
                    result.append(score)
                except Exception as e:
                    logging.error(f"Error evaluating answer relevancy for {dataset[i]}: {e}")

        return np.average(result)
