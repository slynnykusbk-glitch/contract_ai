from contract_review_app.llm.citation_resolver import (
    make_grounding_pack,
    normalize_citations,
)


def test_normalize_citations_dedup_and_whitelist():
    items = [
        {
            "system": "UK",
            "instrument": "Data Protection Act 2018",
            "section": "1",
            "url": "https://www.legislation.gov.uk/ukpga/2018/12/section/1",
        },
        {
            "system": "UK",
            "instrument": "Data Protection Act 2018",
            "section": "1",
            "url": "https://www.legislation.gov.uk/ukpga/2018/12/section/1",
        },
        {
            "instrument": "Unlisted Act",
            "section": "10",
            "url": "https://example.com/bad",
        },
        "Plain Instrument",
    ]
    norm = normalize_citations(items)
    assert [c.id for c in norm] == ["c1", "c2", "c3"]
    assert norm[0].url and "legislation.gov.uk" in norm[0].url
    assert norm[1].url is None
    assert norm[2].instrument == "Plain Instrument"


def test_make_grounding_pack_builds_evidence():
    items = [
        {
            "instrument": "Act A",
            "section": "10",
            "url": "https://www.legislation.gov.uk/a",
        },
        "Act B",
    ]
    gp = make_grounding_pack("What?", "Context", items)
    assert gp["question"] == "What?"
    assert gp["context"] == "Context"
    assert [e["id"] for e in gp["evidence"]] == ["c1", "c2"]
    assert gp["evidence"][0]["source"] == "https://www.legislation.gov.uk/a"
    assert gp["evidence"][1]["source"] == "UK"
