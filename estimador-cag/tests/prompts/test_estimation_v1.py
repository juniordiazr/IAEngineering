import pytest

from app.prompts.loader import render_estimation_prompt
from app.schemas import DetailLevel, EstimationRequest, OutputFormat, ProjectType

DESCRIPTION = "Una plataforma web para gestionar reservas de salas de coworking."


def make_request(**overrides) -> EstimationRequest:
    data = {
        "description": DESCRIPTION,
        "project_type": ProjectType.WEB_SAAS,
        "detail_level": DetailLevel.MEDIUM,
        "output_format": OutputFormat.LINE_ITEMS,
    }
    data.update(overrides)
    return EstimationRequest(**data)


def test_user_prompt_wraps_description_in_project_description_block():
    _, user = render_estimation_prompt(make_request())
    assert f"<project_description>\n{DESCRIPTION}\n</project_description>" in user


def test_description_goes_only_in_user_message():
    system, _ = render_estimation_prompt(make_request())
    assert DESCRIPTION not in system


def test_phases_table_keyword_only_in_that_format():
    system_table, _ = render_estimation_prompt(make_request(output_format=OutputFormat.PHASES_TABLE))
    system_narrative, _ = render_estimation_prompt(make_request(output_format=OutputFormat.NARRATIVE))
    assert "phases_table" in system_table
    assert "confidence_pct" in system_table
    assert "phases_table" not in system_narrative
    assert "confidence_pct" not in system_narrative


def test_detailed_level_adds_assumptions_per_phase():
    system_detailed, _ = render_estimation_prompt(make_request(detail_level=DetailLevel.DETAILED))
    system_summary, _ = render_estimation_prompt(make_request(detail_level=DetailLevel.SUMMARY))
    assert "asunciones por fase" in system_detailed
    assert "asunciones por fase" not in system_summary


def test_system_includes_examples():
    system, _ = render_estimation_prompt(make_request())
    assert "Ejemplos de referencia" in system


def test_unknown_prompt_version_raises():
    with pytest.raises(ValueError):
        render_estimation_prompt(make_request(), version="v99")


def test_version_with_path_traversal_is_rejected():
    with pytest.raises(ValueError):
        render_estimation_prompt(make_request(), version="../v1")