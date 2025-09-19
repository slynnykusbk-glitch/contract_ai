from contract_review_app.core.lx_types import LxDocFeatures, LxFeatureSet


def test_feature_set_defaults():
    feature_set = LxFeatureSet()

    assert feature_set.labels == []
    assert feature_set.parties == []
    assert feature_set.company_numbers == []
    assert feature_set.amounts == []
    assert feature_set.durations == {}
    assert feature_set.law_signals == []
    assert feature_set.jurisdiction is None
    assert feature_set.liability_caps == []
    assert feature_set.carveouts == []

    serialized = feature_set.dict()
    assert serialized["labels"] == []
    assert serialized["parties"] == []
    assert serialized["company_numbers"] == []
    assert serialized["amounts"] == []
    assert serialized["durations"] == {}
    assert serialized["law_signals"] == []
    assert serialized["jurisdiction"] is None
    assert serialized["liability_caps"] == []
    assert serialized["carveouts"] == []


def test_doc_features_defaults():
    doc_features = LxDocFeatures()

    assert doc_features.by_segment == {}

    serialized = doc_features.dict()
    assert serialized["by_segment"] == {}
