from contract_review_app.intake.splitter import split_into_candidate_blocks


def test_clause_segmentation_headings():
    raw = (
        "Confidentiality\nThe parties shall keep secrets.\n\n"
        "Limitation of liability\nEach party's liability is limited.\n\n"
        "VAT/Tax\nVAT will be added to all invoices.\n\n"
        "Data protection\nParties shall comply with GDPR."
    )
    blocks = split_into_candidate_blocks(raw, min_len=10, sentence_split_over=200)
    assert len(blocks) == 4
    assert blocks[0].startswith("Confidentiality")
    assert blocks[1].startswith("Limitation of liability")
    assert blocks[2].startswith("VAT/Tax")
    assert blocks[3].startswith("Data protection")
