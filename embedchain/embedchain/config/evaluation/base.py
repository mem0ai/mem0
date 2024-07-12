from typing import Optional

from embedchain.config.base_config import BaseConfig

ANSWER_RELEVANCY_PROMPT = """
Please provide $num_gen_questions questions from the provided answer.
You must provide the complete question, if are not able to provide the complete question, return empty string ("").
Please only provide one question per line without numbers or bullets to distinguish them.
You must only provide the questions and no other text.

$answer
"""  # noqa:E501


CONTEXT_RELEVANCY_PROMPT = """
Please extract relevant sentences from the provided context that is required to answer the given question.
If no relevant sentences are found, or if you believe the question cannot be answered from the given context, return the empty string ("").
While extracting candidate sentences you're not allowed to make any changes to sentences from given context or make up any sentences.
You must only provide sentences from the given context and nothing else.

Context: $context
Question: $question
"""  # noqa:E501

GROUNDEDNESS_ANSWER_CLAIMS_PROMPT = """
Please provide one or more statements from each sentence of the provided answer.
You must provide the symantically equivalent statements for each sentence of the answer.
You must provide the complete statement, if are not able to provide the complete statement, return empty string ("").
Please only provide one statement per line WITHOUT numbers or bullets.
If the question provided is not being answered in the provided answer, return empty string ("").
You must only provide the statements and no other text.

$question
$answer
"""  # noqa:E501

GROUNDEDNESS_CLAIMS_INFERENCE_PROMPT = """
Given the context and the provided claim statements, please provide a verdict for each claim statement whether it can be completely infered from the given context or not.
Use only "1" (yes), "0" (no) and "-1" (null) for "yes", "no" or "null" respectively.
You must provide one verdict per line, ONLY WITH "1", "0" or "-1" as per your verdict to the given statement and nothing else.
You must provide the verdicts in the same order as the claim statements.

Contexts: 
$context

Claim statements: 
$claim_statements
"""  # noqa:E501


class GroundednessConfig(BaseConfig):
    def __init__(
        self,
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        answer_claims_prompt: str = GROUNDEDNESS_ANSWER_CLAIMS_PROMPT,
        claims_inference_prompt: str = GROUNDEDNESS_CLAIMS_INFERENCE_PROMPT,
    ):
        self.model = model
        self.api_key = api_key
        self.answer_claims_prompt = answer_claims_prompt
        self.claims_inference_prompt = claims_inference_prompt


class AnswerRelevanceConfig(BaseConfig):
    def __init__(
        self,
        model: str = "gpt-4",
        embedder: str = "text-embedding-ada-002",
        api_key: Optional[str] = None,
        num_gen_questions: int = 1,
        prompt: str = ANSWER_RELEVANCY_PROMPT,
    ):
        self.model = model
        self.embedder = embedder
        self.api_key = api_key
        self.num_gen_questions = num_gen_questions
        self.prompt = prompt


class ContextRelevanceConfig(BaseConfig):
    def __init__(
        self,
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        language: str = "en",
        prompt: str = CONTEXT_RELEVANCY_PROMPT,
    ):
        self.model = model
        self.api_key = api_key
        self.language = language
        self.prompt = prompt
