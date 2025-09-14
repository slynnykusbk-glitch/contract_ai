from src.uk_regulation_retriever import UKRegulationRetriever


def test_retrieve_by_topic_and_type():
    retriever = UKRegulationRetriever()
    results = retriever.retrieve("data protection", ["ICO"])
    assert results, "Expected at least one ICO result"
    assert all(r["source_type"] == "ICO" for r in results)


def test_non_uk_sources_filtered_out():
    retriever = UKRegulationRetriever()
    # The topic 'export' only exists for a non-UK entry and should be filtered out
    results = retriever.retrieve("export")
    assert results == []
