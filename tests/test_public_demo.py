"""Acceptance tests for the no-login, explicitly artificial teaching walkthrough."""
import json
from pathlib import Path
import shutil

import pytest

import run_public_demo as demo


@pytest.fixture
def teaching_root(tmp_path):
    (tmp_path/"examples").mkdir()
    shutil.copyfile(demo.ROOT/"examples/hand_worked_inputs.json", tmp_path/"examples/hand_worked_inputs.json")
    return tmp_path


def test_read_only_demo_matches_hand_values_and_diagnoses_every_named_fault(teaching_root):
    before = {str(path.relative_to(teaching_root)): path.read_bytes()
              for path in teaching_root.rglob("*") if path.is_file()}
    result = demo.run_demo(teaching_root, write=False)
    assert result["status"] == "PASS"
    assert result["injected_cases"] == result["detected_cases"] == 5
    assert result["inputs_unchanged"]
    baseline = {row["id"]: row for row in result["baselines"]}
    assert baseline["zero_cost_wealth"]["observed"]["terminal_nav"] == pytest.approx(116.865)
    assert baseline["zero_cost_wealth"]["observed"]["active_total_return_difference"] == pytest.approx(.011025)
    assert baseline["funded_fee"]["observed"]["terminal_nav"] == pytest.approx(99.8)
    assert baseline["funded_fee"]["observed"]["total_cost_dollars"] == pytest.approx(.2)
    assert all(set(row["expected_domain_checks_all"]).issubset(row["blockers"])
               and row["corrected_retest"] == "PASS" for row in result["incidents"])
    assert before == {str(path.relative_to(teaching_root)): path.read_bytes()
                      for path in teaching_root.rglob("*") if path.is_file()}
    assert not (teaching_root/"outputs").exists()
    json.dumps(result, allow_nan=False)


def test_demo_is_independent_of_local_licensed_research_artifacts(teaching_root):
    # Even a malformed private-study manifest must never be opened by this path.
    (teaching_root/"data/wrds").mkdir(parents=True)
    (teaching_root/"outputs/wrds").mkdir(parents=True)
    (teaching_root/"data/wrds/manifest.json").write_text("NOT JSON - PRIVATE STUDY SENTINEL")
    (teaching_root/"outputs/wrds/run_summary.json").write_text("NOT JSON - PRIVATE STUDY SENTINEL")
    result = demo.run_demo(teaching_root, write=False)
    assert result["status"] == "PASS"
    assert "PRIVATE STUDY SENTINEL" not in str(result)


def test_generated_artifacts_are_labeled_and_confined_to_public_demo(teaching_root):
    result = demo.run_demo(teaching_root)
    outputs = teaching_root/"outputs"
    assert {str(path.relative_to(outputs)).replace("\\", "/") for path in outputs.rglob("*") if path.is_file()} == {
        "public_demo/public_demo_receipt.json", "public_demo/public_demo_walkthrough.md"}
    stored = json.loads((outputs/"public_demo/public_demo_receipt.json").read_text(encoding="utf-8"))
    assert stored == result
    assert "ARTIFICIAL" in stored["classification"]
    assert "not real production incidents" in (outputs/"public_demo/public_demo_walkthrough.md").read_text(encoding="utf-8")


def test_generic_exception_is_not_counted_as_successful_diagnosis(teaching_root, monkeypatch):
    original = demo.run_validation

    def generic_failure(root, overrides):
        result = original(root, overrides=overrides)
        if result["status"] == "BLOCK":
            return {"status": "BLOCK", "blockers": ["validator_execution"]}
        return result

    monkeypatch.setattr(demo, "run_validation", generic_failure)
    result = demo.run_demo(teaching_root, write=False)
    assert result["status"] == "BLOCK"
    assert result["detected_cases"] == 0


def test_corrupted_hand_ledger_blocks_demo_instead_of_relabeling_expected_values(teaching_root):
    path = teaching_root/"examples/hand_worked_inputs.json"
    inputs = json.loads(path.read_text(encoding="utf-8"))
    inputs["scenarios"][0]["evaluation_nav"][-1] += 1
    path.write_text(json.dumps(inputs), encoding="utf-8")
    result = demo.run_demo(teaching_root, write=False)
    assert result["status"] == "BLOCK"
    baseline = result["baselines"][0]
    assert baseline["status"] == "BLOCK"
    assert "daily_nav_reconstruction" in baseline["validation"]["blockers"]
    assert not baseline["hand_values_match"]


def test_mutating_validator_cannot_pass_input_immutability_proof(teaching_root, monkeypatch):
    original = demo.run_validation

    def mutate_input(root, overrides):
        result = original(root, overrides=overrides)
        overrides["contract"]["limitations"].append("UNEXPECTED MUTATION")
        return result

    monkeypatch.setattr(demo, "run_validation", mutate_input)
    result = demo.run_demo(teaching_root, write=False)
    assert result["status"] == "BLOCK"
    assert not result["inputs_unchanged"]


@pytest.mark.parametrize("status,exit_code", [("PASS", 0), ("BLOCK", 1)])
def test_cli_exit_status_tracks_release_result(monkeypatch, capsys, status, exit_code):
    def completed_demo(*, write):
        assert not write
        return {"status": status, "baselines": [], "incidents": [], "detected_cases": 0,
                "injected_cases": 0, "inputs_unchanged": True}
    monkeypatch.setattr(demo, "run_demo", completed_demo)
    assert demo.main(["--no-write"]) == exit_code
    assert "ARTIFICIAL" in capsys.readouterr().out


def test_output_directory_cannot_redirect_into_empirical_tree(teaching_root):
    empirical = teaching_root/"outputs/oversight"
    empirical.mkdir(parents=True)
    sentinel = empirical/"public_demo_receipt.json"
    sentinel.write_text("PRESERVE_EMPIRICAL_ARTIFACT", encoding="utf-8")
    try:
        (teaching_root/"outputs/public_demo").symlink_to(empirical, target_is_directory=True)
    except OSError as exc:
        pytest.skip("Host does not permit creating symlinks: "+str(exc.errno))
    with pytest.raises(ValueError, match="must not redirect"):
        demo.run_demo(teaching_root)
    assert sentinel.read_text(encoding="utf-8") == "PRESERVE_EMPIRICAL_ARTIFACT"
