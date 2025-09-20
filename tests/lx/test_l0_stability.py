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

    original_features: LxDocFeatures = extract_l0_features(text, parsed.segments)
    reordered_doc = _reorder_segments(parsed)
    reordered_features: LxDocFeatures = extract_l0_features(
        text, reordered_doc.segments
    )

    def _collect_labels(doc_features: LxDocFeatures) -> dict[int, list[str]]:
        return {sid: list(fs.labels) for sid, fs in doc_features.by_segment.items()}

    def _collect_doc_labels(doc_features: LxDocFeatures) -> set[str]:
        return {
            label
            for fs in doc_features.by_segment.values()
            for label in fs.labels
        }

    assert _collect_doc_labels(original_features) == _collect_doc_labels(
        reordered_features
    )

    original_map = _collect_labels(original_features)
    reordered_map = _collect_labels(reordered_features)
    for seg_id, labels in original_map.items():
        assert labels == reordered_map[seg_id]
