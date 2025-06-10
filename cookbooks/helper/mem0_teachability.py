# Copyright (c) 2023 - 2024, Owners of https://github.com/autogen-ai
#
# SPDX-License-Identifier: Apache-2.0
#
# Portions derived from  https://github.com/microsoft/autogen are under the MIT License.
# SPDX-License-Identifier: MIT
# forked from autogen.agentchat.contrib.capabilities.teachability.Teachability

from typing import Dict, Optional, Union

from autogen.agentchat.assistant_agent import ConversableAgent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen.agentchat.contrib.text_analyzer_agent import TextAnalyzerAgent
from termcolor import colored

from mem0 import Memory


class Mem0Teachability(AgentCapability):
    def __init__(
        self,
        verbosity: Optional[int] = 0,
        reset_db: Optional[bool] = False,
        recall_threshold: Optional[float] = 1.5,
        max_num_retrievals: Optional[int] = 10,
        llm_config: Optional[Union[Dict, bool]] = None,
        agent_id: Optional[str] = None,
        memory_client: Optional[Memory] = None,
    ):
        self.verbosity = verbosity
        self.recall_threshold = recall_threshold
        self.max_num_retrievals = max_num_retrievals
        self.llm_config = llm_config
        self.analyzer = None
        self.teachable_agent = None
        self.agent_id = agent_id
        self.memory = memory_client if memory_client else Memory()

        if reset_db:
            self.memory.reset()

    def add_to_agent(self, agent: ConversableAgent):
        self.teachable_agent = agent
        agent.register_hook(hookable_method="process_last_received_message", hook=self.process_last_received_message)

        if self.llm_config is None:
            self.llm_config = agent.llm_config
        assert self.llm_config, "Teachability requires a valid llm_config."

        self.analyzer = TextAnalyzerAgent(llm_config=self.llm_config)

        agent.update_system_message(
            agent.system_message
            + "\nYou've been given the special ability to remember user teachings from prior conversations."
        )

    def process_last_received_message(self, text: Union[Dict, str]):
        expanded_text = text
        if self.memory.get_all(agent_id=self.agent_id):
            expanded_text = self._consider_memo_retrieval(text)
        self._consider_memo_storage(text)
        return expanded_text

    def _consider_memo_storage(self, comment: Union[Dict, str]):
        response = self._analyze(
            comment,
            "Does any part of the TEXT ask the agent to perform a task or solve a problem? Answer with just one word, yes or no.",
        )

        if "yes" in response.lower():
            advice = self._analyze(
                comment,
                "Briefly copy any advice from the TEXT that may be useful for a similar but different task in the future. But if no advice is present, just respond with 'none'.",
            )

            if "none" not in advice.lower():
                task = self._analyze(
                    comment,
                    "Briefly copy just the task from the TEXT, then stop. Don't solve it, and don't include any advice.",
                )

                general_task = self._analyze(
                    task,
                    "Summarize very briefly, in general terms, the type of task described in the TEXT. Leave out details that might not appear in a similar problem.",
                )

                if self.verbosity >= 1:
                    print(colored("\nREMEMBER THIS TASK-ADVICE PAIR", "light_yellow"))
                self.memory.add(
                    [{"role": "user", "content": f"Task: {general_task}\nAdvice: {advice}"}], agent_id=self.agent_id
                )

        response = self._analyze(
            comment,
            "Does the TEXT contain information that could be committed to memory? Answer with just one word, yes or no.",
        )

        if "yes" in response.lower():
            question = self._analyze(
                comment,
                "Imagine that the user forgot this information in the TEXT. How would they ask you for this information? Include no other text in your response.",
            )

            answer = self._analyze(
                comment, "Copy the information from the TEXT that should be committed to memory. Add no explanation."
            )

            if self.verbosity >= 1:
                print(colored("\nREMEMBER THIS QUESTION-ANSWER PAIR", "light_yellow"))
            self.memory.add(
                [{"role": "user", "content": f"Question: {question}\nAnswer: {answer}"}], agent_id=self.agent_id
            )

    def _consider_memo_retrieval(self, comment: Union[Dict, str]):
        if self.verbosity >= 1:
            print(colored("\nLOOK FOR RELEVANT MEMOS, AS QUESTION-ANSWER PAIRS", "light_yellow"))
        memo_list = self._retrieve_relevant_memos(comment)

        response = self._analyze(
            comment,
            "Does any part of the TEXT ask the agent to perform a task or solve a problem? Answer with just one word, yes or no.",
        )

        if "yes" in response.lower():
            if self.verbosity >= 1:
                print(colored("\nLOOK FOR RELEVANT MEMOS, AS TASK-ADVICE PAIRS", "light_yellow"))
            task = self._analyze(
                comment, "Copy just the task from the TEXT, then stop. Don't solve it, and don't include any advice."
            )

            general_task = self._analyze(
                task,
                "Summarize very briefly, in general terms, the type of task described in the TEXT. Leave out details that might not appear in a similar problem.",
            )

            memo_list.extend(self._retrieve_relevant_memos(general_task))

        memo_list = list(set(memo_list))
        return comment + self._concatenate_memo_texts(memo_list)

    def _retrieve_relevant_memos(self, input_text: str) -> list:
        search_results = self.memory.search(input_text, agent_id=self.agent_id, limit=self.max_num_retrievals)
        memo_list = [result["memory"] for result in search_results if result["score"] <= self.recall_threshold]

        if self.verbosity >= 1 and not memo_list:
            print(colored("\nTHE CLOSEST MEMO IS BEYOND THE THRESHOLD:", "light_yellow"))
            if search_results["results"]:
                print(search_results["results"][0])
            print()

        return memo_list

    def _concatenate_memo_texts(self, memo_list: list) -> str:
        memo_texts = ""
        if memo_list:
            info = "\n# Memories that might help\n"
            for memo in memo_list:
                info += f"- {memo}\n"
            if self.verbosity >= 1:
                print(colored(f"\nMEMOS APPENDED TO LAST MESSAGE...\n{info}\n", "light_yellow"))
            memo_texts += "\n" + info
        return memo_texts

    def _analyze(self, text_to_analyze: Union[Dict, str], analysis_instructions: Union[Dict, str]):
        self.analyzer.reset()
        self.teachable_agent.send(
            recipient=self.analyzer, message=text_to_analyze, request_reply=False, silent=(self.verbosity < 2)
        )
        self.teachable_agent.send(
            recipient=self.analyzer, message=analysis_instructions, request_reply=True, silent=(self.verbosity < 2)
        )
        return self.teachable_agent.last_message(self.analyzer)["content"]
