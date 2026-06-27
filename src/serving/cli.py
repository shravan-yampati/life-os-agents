"""Command-line interface for the RAG pipeline.

Usage (from the rag-lab directory):
    python -m src.serving.cli ingest data/sample_docs/aurora_fund.md
    python -m src.serving.cli ask "What is the expense ratio?"
    python -m src.serving.cli status
    python -m src.serving.cli clear
"""

import argparse

from src.config import settings
from src.retrieval.naive import NaiveRAG


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rag-lab", description="Naive RAG pipeline CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Ingest a .txt or .md document")
    ingest_p.add_argument("path", help="Path to the document")

    ask_p = sub.add_parser("ask", help="Ask a question over ingested documents")
    ask_p.add_argument("question", help="The question to answer")
    ask_p.add_argument("--top-k", type=int, default=4, help="Chunks to retrieve")

    sub.add_parser("status", help="Show backend configuration and chunk count")
    sub.add_parser("clear", help="Delete all ingested chunks")

    args = parser.parse_args()
    rag = NaiveRAG(top_k=getattr(args, "top_k", 4))

    if args.command == "ingest":
        count = rag.ingest(args.path)
        print(f"Ingested {count} chunks from {args.path}")
        print(f"Store now holds {rag.store.count()} chunks total.")
    elif args.command == "ask":
        response = rag.ask(args.question)
        print(f"\nANSWER:\n{response.answer}\n")
        if response.sources:
            print("SOURCES:")
            for r in response.sources:
                preview = r.text[:80].replace("\n", " ")
                print(f"  [{r.score:.3f}] {r.source}: {preview}...")
    elif args.command == "status":
        print(f"CLOUD_PROVIDER : {settings.CLOUD_PROVIDER}")
        print(f"VECTOR_BACKEND : {settings.VECTOR_BACKEND}")
        print(f"Chunks stored  : {rag.store.count()}")
    elif args.command == "clear":
        rag.store.clear()
        print("Vector store cleared.")


if __name__ == "__main__":
    main()
