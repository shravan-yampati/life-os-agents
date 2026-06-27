from src.providers.local import LocalEmbeddings, LocalLLM


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot  # vectors are already L2-normalized


def test_embeddings_are_deterministic():
    emb = LocalEmbeddings()
    assert emb.embed_query("expense ratio") == emb.embed_query("expense ratio")


def test_embeddings_reflect_lexical_similarity():
    emb = LocalEmbeddings()
    query = emb.embed_query("What is the fund expense ratio?")
    relevant = emb.embed_query("The fund charges an annual expense ratio of 0.72%.")
    irrelevant = emb.embed_query("Bananas are rich in potassium and grow in clusters.")
    assert _cosine(query, relevant) > _cosine(query, irrelevant)


def test_embed_documents_matches_embed_query():
    emb = LocalEmbeddings()
    docs = ["alpha beta", "gamma delta"]
    assert emb.embed_documents(docs) == [emb.embed_query(d) for d in docs]


def test_llm_extracts_relevant_sentence():
    llm = LocalLLM()
    prompt = (
        "Answer using the context.\n\n"
        "CONTEXT:\nThe sky is blue. The fund charges an expense ratio of "
        "0.72 percent. Cats sleep a lot.\n\n"
        "QUESTION: What is the expense ratio?"
    )
    answer = llm.generate(prompt)
    assert "0.72" in answer
    assert "Cats" not in answer


def test_llm_stream_matches_generate():
    llm = LocalLLM()
    prompt = "CONTEXT:\nParis is the capital of France.\n\nQUESTION: capital of France?"
    assert "".join(llm.stream(prompt)).strip() == llm.generate(prompt)
