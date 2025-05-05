import argparse
import json
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI
from prompts import ANSWER_PROMPT_ZEP
from tqdm import tqdm
from zep_cloud import EntityEdge, EntityNode
from zep_cloud.client import Zep

load_dotenv()

TEMPLATE = """
FACTS and ENTITIES represent relevant context to the current conversation.

# These are the most relevant facts and their valid date ranges
# format: FACT (Date range: from - to)

{facts}


# These are the most relevant entities
# ENTITY_NAME: entity summary

{entities}

"""


class ZepSearch:
    def __init__(self):
        self.zep_client = Zep(api_key=os.getenv("ZEP_API_KEY"))
        self.results = defaultdict(list)
        self.openai_client = OpenAI()

    def format_edge_date_range(self, edge: EntityEdge) -> str:
        # return f"{datetime(edge.valid_at).strftime('%Y-%m-%d %H:%M:%S') if edge.valid_at else 'date unknown'} - {(edge.invalid_at.strftime('%Y-%m-%d %H:%M:%S') if edge.invalid_at else 'present')}"
        return f"{edge.valid_at if edge.valid_at else 'date unknown'} - {(edge.invalid_at if edge.invalid_at else 'present')}"

    def compose_search_context(self, edges: list[EntityEdge], nodes: list[EntityNode]) -> str:
        facts = [f"  - {edge.fact} ({self.format_edge_date_range(edge)})" for edge in edges]
        entities = [f"  - {node.name}: {node.summary}" for node in nodes]
        return TEMPLATE.format(facts="\n".join(facts), entities="\n".join(entities))

    def search_memory(self, run_id, idx, query, max_retries=3, retry_delay=1):
        start_time = time.time()
        retries = 0
        while retries < max_retries:
            try:
                user_id = f"run_id_{run_id}_experiment_user_{idx}"
                edges_results = (
                    self.zep_client.graph.search(
                        user_id=user_id, reranker="cross_encoder", query=query, scope="edges", limit=20
                    )
                ).edges
                node_results = (
                    self.zep_client.graph.search(user_id=user_id, reranker="rrf", query=query, scope="nodes", limit=20)
                ).nodes
                context = self.compose_search_context(edges_results, node_results)
                break
            except Exception as e:
                print("Retrying...")
                retries += 1
                if retries >= max_retries:
                    raise e
                time.sleep(retry_delay)

        end_time = time.time()

        return context, end_time - start_time

    def process_question(self, run_id, val, idx):
        question = val.get("question", "")
        answer = val.get("answer", "")
        category = val.get("category", -1)
        evidence = val.get("evidence", [])
        adversarial_answer = val.get("adversarial_answer", "")

        response, search_memory_time, response_time, context = self.answer_question(run_id, idx, question)

        result = {
            "question": question,
            "answer": answer,
            "category": category,
            "evidence": evidence,
            "response": response,
            "adversarial_answer": adversarial_answer,
            "search_memory_time": search_memory_time,
            "response_time": response_time,
            "context": context,
        }

        return result

    def answer_question(self, run_id, idx, question):
        context, search_memory_time = self.search_memory(run_id, idx, question)

        template = Template(ANSWER_PROMPT_ZEP)
        answer_prompt = template.render(memories=context, question=question)

        t1 = time.time()
        response = self.openai_client.chat.completions.create(
            model=os.getenv("MODEL"), messages=[{"role": "system", "content": answer_prompt}], temperature=0.0
        )
        t2 = time.time()
        response_time = t2 - t1
        return response.choices[0].message.content, search_memory_time, response_time, context

    def process_data_file(self, file_path, run_id, output_file_path):
        with open(file_path, "r") as f:
            data = json.load(f)

        for idx, item in tqdm(enumerate(data), total=len(data), desc="Processing conversations"):
            qa = item["qa"]

            for question_item in tqdm(
                qa, total=len(qa), desc=f"Processing questions for conversation {idx}", leave=False
            ):
                result = self.process_question(run_id, question_item, idx)
                self.results[idx].append(result)

                # Save results after each question is processed
                with open(output_file_path, "w") as f:
                    json.dump(self.results, f, indent=4)

        # Final save at the end
        with open(output_file_path, "w") as f:
            json.dump(self.results, f, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", type=str, required=True)
    args = parser.parse_args()
    zep_search = ZepSearch()
    zep_search.process_data_file("../../dataset/locomo10.json", args.run_id, "results/zep_search_results.json")
