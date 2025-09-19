from contract_review_app.analysis.parser import parse_text, ParsedDoc
from contract_review_app.analysis.lx_features import extract_l0_features, LxDocFeatures


def _reorder_segments(doc: ParsedDoc) -> ParsedDoc:
    reordered = list(doc.segments)
    reordered.reverse()
    # preserve ids but change order
    doc_copy = ParsedDoc(
        normalized_text=doc.normalized_text,
        offset_map=doc.offset_map,
        segments=reordered,
    )
    return doc_copy


def test_segment_label_mapping_is_stable():
    text = (
        "Payment shall be made within sixty (60) days of receipt of invoice.\n"
        "This Agreement shall remain in force for forty-five (45) days from execution."
    )
    parsed = parse_text(text)

    original_features: LxDocFeatures = extract_l0_features(parsed)
    reordered_doc = _reorder_segments(parsed)
    reordered_features: LxDocFeatures = extract_l0_features(reordered_doc)

    assert original_features.labels == reordered_features.labels

    for seg_id, features in original_features.segments.items():
        assert features.labels == reordered_features.segments[seg_id].labels
