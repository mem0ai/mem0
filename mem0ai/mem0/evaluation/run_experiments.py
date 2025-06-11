import argparse
import os

from src.langmem import LangMemManager
from src.memzero.add import MemoryADD
from src.memzero.search import MemorySearch
from src.openai.predict import OpenAIPredict
from src.rag import RAGManager
from src.utils import METHODS, TECHNIQUES
from src.zep.add import ZepAdd
from src.zep.search import ZepSearch


class Experiment:
    def __init__(self, technique_type, chunk_size):
        self.technique_type = technique_type
        self.chunk_size = chunk_size

    def run(self):
        print(f"Running experiment with technique: {self.technique_type}, chunk size: {self.chunk_size}")


def main():
    parser = argparse.ArgumentParser(description="Run memory experiments")
    parser.add_argument("--technique_type", choices=TECHNIQUES, default="mem0", help="Memory technique to use")
    parser.add_argument("--method", choices=METHODS, default="add", help="Method to use")
    parser.add_argument("--chunk_size", type=int, default=1000, help="Chunk size for processing")
    parser.add_argument("--output_folder", type=str, default="results/", help="Output path for results")
    parser.add_argument("--top_k", type=int, default=30, help="Number of top memories to retrieve")
    parser.add_argument("--filter_memories", action="store_true", default=False, help="Whether to filter memories")
    parser.add_argument("--is_graph", action="store_true", default=False, help="Whether to use graph-based search")
    parser.add_argument("--num_chunks", type=int, default=1, help="Number of chunks to process")

    args = parser.parse_args()

    # Add your experiment logic here
    print(f"Running experiments with technique: {args.technique_type}, chunk size: {args.chunk_size}")

    if args.technique_type == "mem0":
        if args.method == "add":
            memory_manager = MemoryADD(data_path="dataset/locomo10.json", is_graph=args.is_graph)
            memory_manager.process_all_conversations()
        elif args.method == "search":
            output_file_path = os.path.join(
                args.output_folder,
                f"mem0_results_top_{args.top_k}_filter_{args.filter_memories}_graph_{args.is_graph}.json",
            )
            memory_searcher = MemorySearch(output_file_path, args.top_k, args.filter_memories, args.is_graph)
            memory_searcher.process_data_file("dataset/locomo10.json")
    elif args.technique_type == "rag":
        output_file_path = os.path.join(args.output_folder, f"rag_results_{args.chunk_size}_k{args.num_chunks}.json")
        rag_manager = RAGManager(data_path="dataset/locomo10_rag.json", chunk_size=args.chunk_size, k=args.num_chunks)
        rag_manager.process_all_conversations(output_file_path)
    elif args.technique_type == "langmem":
        output_file_path = os.path.join(args.output_folder, "langmem_results.json")
        langmem_manager = LangMemManager(dataset_path="dataset/locomo10_rag.json")
        langmem_manager.process_all_conversations(output_file_path)
    elif args.technique_type == "zep":
        if args.method == "add":
            zep_manager = ZepAdd(data_path="dataset/locomo10.json")
            zep_manager.process_all_conversations("1")
        elif args.method == "search":
            output_file_path = os.path.join(args.output_folder, "zep_search_results.json")
            zep_manager = ZepSearch()
            zep_manager.process_data_file("dataset/locomo10.json", "1", output_file_path)
    elif args.technique_type == "openai":
        output_file_path = os.path.join(args.output_folder, "openai_results.json")
        openai_manager = OpenAIPredict()
        openai_manager.process_data_file("dataset/locomo10.json", output_file_path)
    else:
        raise ValueError(f"Invalid technique type: {args.technique_type}")


if __name__ == "__main__":
    main()
