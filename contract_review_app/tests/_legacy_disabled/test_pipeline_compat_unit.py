from contract_review_app.engine.pipeline_compat import to_panel_shape


def test_to_panel_shape_minimal_ok():
    ssot = {
        "summary_status": "OK",
        "summary_risk": "medium",
        "summary_score": 0,
        "analyses": [
            {
                "clause_type": "termination",
                "status": "OK",
                "risk_level": "low",
                "score": 10,
                "findings": [{"code": "T-001", "message": "ok"}],
                "span": {"start": 5, "end": 15},
                "title": "Termination",
            }
        ],
        "index": {
            "clauses": [
                {
                    "id": "c1",
                    "type": "termination",
                    "title": "Termination",
                    "span": {"start": 5, "end": 15},
                }
            ]
        },
        "text": "abcde0123456789",
    }
    analysis, results, clauses = to_panel_shape(ssot)
    assert set(analysis.keys()) == {"status", "risk_level", "score", "findings"}
    assert "termination" in results and set(results["termination"].keys()) == {
        "status",
        "risk_level",
        "score",
        "findings",
    }
    assert clauses and {"id", "type", "title", "span"} <= set(clauses[0].keys())
    sp = clauses[0]["span"]
    assert isinstance(sp["start"], int) and sp["start"] >= 0
    assert isinstance(sp["length"], int) and sp["length"] >= 0
