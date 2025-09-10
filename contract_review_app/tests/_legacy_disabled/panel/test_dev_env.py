from pathlib import Path


def test_run_dev_sets_llm_mock(tmp_path):
    # Проверим, что команда содержит CONTRACTAI_LLM_API=mock (по тексту файла)
    ps = Path("RUN_DEV.ps1")
    assert ps.exists()
    text = ps.read_text(encoding="utf-8").lower()
    assert "contractai_llm_api" in text and "mock" in text
