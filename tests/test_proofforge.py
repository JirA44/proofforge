from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.main import app
from apps.api.models import (
    ArgumentCreate,
    EntailmentCheckCreate,
    FormulaComparisonCreate,
    InconsistencyAnalysisCreate,
    MultiArgumentCoherenceCreate,
    ProofObligationCoverageDossierCreate,
    ProofStabilityDossierCreate,
    PremiseSetCreate,
    ProofDependencyDossierCreate,
    PropositionCreate,
    VerificationCreate,
)
from apps.api.repository import Repository


def test_tautology_is_verified_and_idempotent():
    with TemporaryDirectory() as tmp:
        repo=Repository(Path(tmp)/"proof.db")
        proposition=repo.create_proposition(PropositionCreate(name="Excluded middle",statement="P or not P",formal_expression="P | !P",variables=["P"]))
        first=repo.verify(VerificationCreate(proposition_id=proposition.id))
        assert first.verdict == "VERIFIED" and first.valuations_checked == 2
        second=repo.verify(VerificationCreate(proposition_id=proposition.id))
        assert second.id == first.id and second.idempotent_replay is True


def test_non_tautology_returns_machine_counterexample():
    with TemporaryDirectory() as tmp:
        repo=Repository(Path(tmp)/"proof.db")
        proposition=repo.create_proposition(PropositionCreate(name="Implication",statement="P implies Q",formal_expression="P -> Q",variables=["P","Q"]))
        result=repo.verify(VerificationCreate(proposition_id=proposition.id))
        assert result.verdict == "REFUTED"
        assert result.counterexample == {"P":True,"Q":False}


def test_undeclared_variable_is_rejected_not_verified():
    with TemporaryDirectory() as tmp:
        repo=Repository(Path(tmp)/"proof.db")
        proposition=repo.create_proposition(PropositionCreate(name="Invalid",statement="Unknown variable",formal_expression="P | Q",variables=["P"]))
        try: repo.verify(VerificationCreate(proposition_id=proposition.id))
        except ValueError as exc: assert "undeclared variable" in str(exc)
        else: raise AssertionError("invalid expression verified")


def create_argument(repo, premises, conclusion):
    return repo.create_argument(
        ArgumentCreate(
            name="Formal argument",
            premises=premises,
            conclusion=conclusion,
            variables=["P", "Q"],
        )
    )


def test_modus_ponens_is_entailed_and_idempotent():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        argument = create_argument(repo, ["P -> Q", "P"], "Q")
        first = repo.check_entailment(EntailmentCheckCreate(argument_id=argument.id))
        assert first.verdict == "ENTAILED"
        assert first.premise_models == 1
        replay = repo.check_entailment(EntailmentCheckCreate(argument_id=argument.id))
        assert replay.id == first.id
        assert replay.idempotent_replay is True


def test_invalid_argument_returns_counterexample():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        argument = create_argument(repo, ["P -> Q"], "P")
        result = repo.check_entailment(EntailmentCheckCreate(argument_id=argument.id))
        assert result.verdict == "NOT_ENTAILED"
        assert result.counterexample == {"P": False, "Q": False}


def test_inconsistent_premises_are_not_reported_as_entailed():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        argument = create_argument(repo, ["P", "!P"], "Q")
        result = repo.check_entailment(EntailmentCheckCreate(argument_id=argument.id))
        assert result.verdict == "INCONSISTENT_PREMISES"
        assert result.premise_models == 0
        assert result.counterexample is None


def test_client_cannot_submit_entailment_verdict():
    with pytest.raises(ValidationError):
        EntailmentCheckCreate(argument_id="argument", verdict="ENTAILED")


def test_demorgan_formulas_are_equivalent_and_idempotent():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        request = FormulaComparisonCreate(
            name="De Morgan",
            left_expression="!(P & Q)",
            right_expression="!P | !Q",
            variables=["P", "Q"],
        )
        first = repo.compare(request)
        assert first.verdict == "EQUIVALENT"
        assert first.valuations_checked == 4
        assert first.counterexample is None
        replay = repo.compare(request)
        assert replay.id == first.id
        assert replay.idempotent_replay is True


def test_non_equivalent_formulas_return_detailed_counterexample():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        result = repo.compare(
            FormulaComparisonCreate(
                name="Conjunction versus disjunction",
                left_expression="P & Q",
                right_expression="P | Q",
                variables=["P", "Q"],
            )
        )
        assert result.verdict == "NOT_EQUIVALENT"
        assert result.counterexample.valuation == {"P": False, "Q": True}
        assert result.counterexample.left_value is False
        assert result.counterexample.right_value is True


def test_formula_comparison_rejects_undeclared_variable():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        with pytest.raises(ValueError, match="undeclared variable"):
            repo.compare(
                FormulaComparisonCreate(
                    name="Invalid comparison",
                    left_expression="P | R",
                    right_expression="P",
                    variables=["P"],
                )
            )


def test_client_cannot_submit_formula_comparison_verdict():
    with pytest.raises(ValidationError):
        FormulaComparisonCreate(
            name="Client verdict",
            left_expression="P",
            right_expression="P",
            variables=["P"],
            verdict="EQUIVALENT",
        )


def create_premise_set(repo, premises, variables=None):
    return repo.create_premise_set(
        PremiseSetCreate(
            name="Consistency fixture",
            premises=premises,
            variables=variables or ["P", "Q"],
        )
    )


def test_consistent_premises_return_machine_assignment_and_replay():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        premise_set = create_premise_set(repo, ["P -> Q", "P"])
        request = InconsistencyAnalysisCreate(premise_set_id=premise_set.id)
        first = repo.analyze_premise_set(request)
        assert first.verdict == "CONSISTENT"
        assert first.satisfying_assignment == {"P": True, "Q": True}
        assert first.minimal_core == []
        assert first.minimality_verified is False
        replay = repo.analyze_premise_set(request)
        assert replay.id == first.id and replay.idempotent_replay is True


def test_irrelevant_premise_is_removed_from_minimal_core():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        premise_set = create_premise_set(repo, ["P", "!P", "Q"])
        result = repo.analyze_premise_set(
            InconsistencyAnalysisCreate(premise_set_id=premise_set.id)
        )
        assert result.verdict == "INCONSISTENT"
        assert result.core_indices == [0, 1]
        assert result.minimal_core == ["P", "!P"]
        assert result.minimality_verified is True
        assert len(result.analysis_hash) == 64


def test_implication_conflict_core_is_inclusion_minimal():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        premise_set = create_premise_set(repo, ["P -> Q", "P", "!Q", "Q | !Q"])
        result = repo.analyze_premise_set(
            InconsistencyAnalysisCreate(premise_set_id=premise_set.id)
        )
        assert result.minimal_core == ["P -> Q", "P", "!Q"]
        assert all(witness.valuation is not None for witness in result.necessity_witnesses)
        assert {witness.removed_index for witness in result.necessity_witnesses} == {0, 1, 2}


def test_each_core_premise_has_a_necessity_witness():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        premise_set = create_premise_set(repo, ["P", "!P"])
        result = repo.analyze_premise_set(
            InconsistencyAnalysisCreate(premise_set_id=premise_set.id)
        )
        witnesses = {item.removed_premise: item.valuation for item in result.necessity_witnesses}
        assert witnesses["P"]["P"] is False
        assert witnesses["!P"]["P"] is True


def test_invalid_premise_is_rejected_instead_of_receiving_a_verdict():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        premise_set = create_premise_set(repo, ["P & R"])
        with pytest.raises(ValueError, match="undeclared variable"):
            repo.analyze_premise_set(
                InconsistencyAnalysisCreate(premise_set_id=premise_set.id)
            )


def test_client_cannot_submit_core_or_verdict():
    with pytest.raises(ValidationError):
        InconsistencyAnalysisCreate.model_validate(
            {
                "premise_set_id": "set-1",
                "verdict": "INCONSISTENT",
                "minimal_core": ["P", "!P"],
            }
        )


def test_premise_sets_and_analyses_are_database_immutable():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        premise_set = create_premise_set(repo, ["P", "!P"])
        analysis = repo.analyze_premise_set(
            InconsistencyAnalysisCreate(premise_set_id=premise_set.id)
        )
        with pytest.raises(Exception, match="immutable"):
            with repo.connect() as connection:
                connection.execute(
                    "UPDATE inconsistency_analyses SET verdict='CONSISTENT' WHERE id=?",
                    (analysis.id,),
                )


def test_unknown_premise_set_and_analysis_are_rejected():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        with pytest.raises(KeyError, match="premise set not found"):
            repo.analyze_premise_set(
                InconsistencyAnalysisCreate(premise_set_id="missing")
            )
        with pytest.raises(KeyError, match="inconsistency analysis not found"):
            repo.get_inconsistency_analysis("missing")


def make_entailment(repo, name, premises, conclusion):
    argument = repo.create_argument(
        ArgumentCreate(
            name=name,
            premises=premises,
            conclusion=conclusion,
            variables=["P", "Q"],
        )
    )
    return repo.check_entailment(EntailmentCheckCreate(argument_id=argument.id))


def test_dependency_dossier_closes_root_and_replays_order_independently():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        root = make_entailment(repo, "root", ["P", "P -> Q"], "Q")
        premise = make_entailment(repo, "premise", ["P"], "P")
        rule = make_entailment(repo, "rule", ["P -> Q"], "P -> Q")
        first = repo.create_proof_dependency_dossier(
            ProofDependencyDossierCreate(
                root_entailment_id=root.id,
                supporting_entailment_ids=[premise.id, rule.id],
            )
        )
        assert first.qualification == "CLOSED"
        assert first.open_assumptions == []
        assert len(first.edges) == 2
        replay = repo.create_proof_dependency_dossier(
            ProofDependencyDossierCreate(
                root_entailment_id=root.id,
                supporting_entailment_ids=[rule.id, premise.id],
            )
        )
        assert replay.id == first.id and replay.idempotent_replay is True


def test_dependency_dossier_reports_open_root_assumptions():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        root = make_entailment(repo, "root-open", ["P", "P -> Q"], "Q")
        premise = make_entailment(repo, "only-premise", ["P"], "P")
        result = repo.create_proof_dependency_dossier(
            ProofDependencyDossierCreate(
                root_entailment_id=root.id,
                supporting_entailment_ids=[premise.id],
            )
        )
        assert result.qualification == "OPEN_ASSUMPTIONS"
        assert result.open_assumptions == ["P -> Q"]


def test_dependency_dossier_marks_unused_supports():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        root = make_entailment(repo, "root-unused", ["P"], "P | Q")
        p_support = make_entailment(repo, "p-support", ["P"], "P")
        q_support = make_entailment(repo, "q-unused", ["Q"], "Q")
        result = repo.create_proof_dependency_dossier(
            ProofDependencyDossierCreate(
                root_entailment_id=root.id,
                supporting_entailment_ids=[p_support.id, q_support.id],
            )
        )
        assert result.qualification == "CLOSED"
        assert result.unused_entailment_ids == [q_support.id]


def test_dependency_dossier_detects_support_cycle():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        root = make_entailment(repo, "root-cycle", ["P"], "P | Q")
        first = make_entailment(repo, "cycle-a", ["P & P"], "P")
        second = make_entailment(repo, "cycle-b", ["P"], "P & P")
        result = repo.create_proof_dependency_dossier(
            ProofDependencyDossierCreate(
                root_entailment_id=root.id,
                supporting_entailment_ids=[first.id, second.id],
            )
        )
        assert result.qualification == "CYCLIC"
        assert result.cycles


def test_non_entailed_support_invalidates_dependency_dossier():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        root = make_entailment(repo, "root-invalid", ["P"], "P | Q")
        invalid = make_entailment(repo, "invalid-support", ["Q"], "P")
        assert invalid.verdict == "NOT_ENTAILED"
        result = repo.create_proof_dependency_dossier(
            ProofDependencyDossierCreate(
                root_entailment_id=root.id,
                supporting_entailment_ids=[invalid.id],
            )
        )
        assert result.qualification == "INVALID"


def test_dependency_dossier_rejects_missing_or_duplicate_ids():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        with pytest.raises(KeyError, match="entailment not found"):
            repo.create_proof_dependency_dossier(
                ProofDependencyDossierCreate(root_entailment_id="missing")
            )
    with pytest.raises(ValidationError):
        ProofDependencyDossierCreate(
            root_entailment_id="root", supporting_entailment_ids=["a", "a"]
        )


def test_client_cannot_submit_dependency_qualification_or_results():
    with pytest.raises(ValidationError):
        ProofDependencyDossierCreate.model_validate(
            {
                "root_entailment_id": "root",
                "qualification": "CLOSED",
                "open_assumptions": [],
            }
        )


def test_dependency_request_is_bounded_to_fifty_total_proofs():
    with pytest.raises(ValidationError):
        ProofDependencyDossierCreate(
            root_entailment_id="root",
            supporting_entailment_ids=[f"support-{index}" for index in range(50)],
        )


def test_dependency_dossiers_are_immutable_and_audited():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        root = make_entailment(repo, "root-immutable", ["P"], "P | Q")
        support = make_entailment(repo, "support-immutable", ["P"], "P")
        dossier = repo.create_proof_dependency_dossier(
            ProofDependencyDossierCreate(
                root_entailment_id=root.id,
                supporting_entailment_ids=[support.id],
            )
        )
        assert repo.get_proof_dependency_dossier(dossier.id).dossier_hash == dossier.dossier_hash
        assert repo.list_proof_dependency_dossiers()[0].id == dossier.id
        with pytest.raises(Exception, match="immutable"):
            with repo.connect() as connection:
                connection.execute(
                    "UPDATE proof_dependency_dossiers SET qualification='INVALID' WHERE id=?",
                    (dossier.id,),
                )
        with repo.connect() as connection:
            audit = connection.execute(
                "SELECT * FROM audit_events WHERE entity_id=?", (dossier.id,)
            ).fetchone()
        assert audit["event_type"] == "PROOF_DEPENDENCIES_ANALYZED"


def test_multi_argument_consistent_returns_explicit_model():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_entailment(repo, "coherent-p", ["P"], "P")
        second = make_entailment(repo, "coherent-q", ["Q"], "Q")
        dossier = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[first.id, second.id])
        )
        assert dossier.qualification == "CONSISTENT"
        assert dossier.satisfying_assignment == {"P": True, "Q": True}
        assert dossier.contradiction_witnesses == []
        assert all(proof.verification_valid for proof in dossier.proofs)


def test_multi_argument_detects_logical_negation_with_witnesses():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        positive = make_entailment(repo, "positive", ["P"], "P")
        negative = make_entailment(repo, "negative", ["!P"], "!P")
        dossier = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[positive.id, negative.id])
        )
        assert dossier.qualification == "CONTRADICTORY"
        witness = dossier.contradiction_witnesses[0]
        assert witness.kind == "LOGICAL_NEGATION_OR_INCOMPATIBILITY"
        assert set(witness.conclusions) == {"P", "!P"}
        assert all(item.valuation is not None for item in witness.necessity_witnesses)


def test_multi_argument_detects_joint_impossibility_beyond_pairs():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        disjunction = make_entailment(repo, "disjunction", ["P | Q"], "P | Q")
        not_p = make_entailment(repo, "not-p", ["!P"], "!P")
        not_q = make_entailment(repo, "not-q", ["!Q"], "!Q")
        dossier = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(
                entailment_ids=[disjunction.id, not_p.id, not_q.id]
            )
        )
        assert dossier.qualification == "CONTRADICTORY"
        witness = dossier.contradiction_witnesses[0]
        assert witness.kind == "JOINT_IMPOSSIBILITY"
        assert len(witness.conclusions) == 3
        assert len(witness.necessity_witnesses) == 3


def test_multi_argument_non_entailed_proof_is_insufficient():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        valid = make_entailment(repo, "valid", ["P"], "P")
        invalid = make_entailment(repo, "invalid", ["Q"], "P")
        dossier = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[valid.id, invalid.id])
        )
        assert dossier.qualification == "INSUFFICIENT"
        assert any("conclusion_not_established" in issue for issue in dossier.issues)
        assert dossier.valuations_checked == 0


def test_multi_argument_recalculates_and_rejects_corrupted_hash():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_entailment(repo, "integrity-a", ["P"], "P")
        second = make_entailment(repo, "integrity-b", ["Q"], "Q")
        with repo.connect() as connection:
            connection.execute("DROP TRIGGER entailments_no_update")
            connection.execute(
                "UPDATE entailment_checks SET entailment_hash=? WHERE id=?",
                ("0" * 64, first.id),
            )
        dossier = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[first.id, second.id])
        )
        assert dossier.qualification == "INSUFFICIENT"
        assert next(p for p in dossier.proofs if p.entailment_id == first.id).verification_valid is False


def test_multi_argument_combined_variable_bound_is_incompatible():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first_argument = repo.create_argument(
            ArgumentCreate(
                name="eight variables",
                premises=["A"], conclusion="A",
                variables=["A", "B", "C", "D", "E", "F", "G", "H"],
            )
        )
        second_argument = repo.create_argument(
            ArgumentCreate(name="ninth variable", premises=["I"], conclusion="I", variables=["I"])
        )
        first = repo.check_entailment(EntailmentCheckCreate(argument_id=first_argument.id))
        second = repo.check_entailment(EntailmentCheckCreate(argument_id=second_argument.id))
        dossier = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[first.id, second.id])
        )
        assert dossier.qualification == "INCOMPATIBLE"
        assert "combined_variable_limit_exceeded:8" in dossier.issues


def test_multi_argument_request_is_strict_unique_and_bounded():
    invalid = [
        {"entailment_ids": ["one"]},
        {"entailment_ids": ["same", "same"]},
        {"entailment_ids": [str(index) for index in range(51)]},
        {"entailment_ids": ["one", "two"], "qualification": "CONSISTENT"},
        {"entailment_ids": ["one", "two"], "witnesses": []},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            MultiArgumentCoherenceCreate.model_validate(payload)


def test_multi_argument_snapshot_is_order_independent_and_audited_once():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_entailment(repo, "order-a", ["P"], "P")
        second = make_entailment(repo, "order-b", ["Q"], "Q")
        created = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[second.id, first.id])
        )
        replay = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[first.id, second.id])
        )
        assert replay.id == created.id and replay.idempotent_replay is True
        assert created.entailment_ids == sorted([first.id, second.id])
        assert len(created.snapshot_hash) == len(created.dossier_hash) == 64
        with repo.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE event_type='MULTI_ARGUMENT_COHERENCE_ANALYZED'"
            ).fetchone()[0]
        assert count == 1


def test_multi_argument_dossier_is_immutable_gettable_and_listed():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_entailment(repo, "immutable-a", ["P"], "P")
        second = make_entailment(repo, "immutable-b", ["Q"], "Q")
        dossier = repo.create_multi_argument_coherence_dossier(
            MultiArgumentCoherenceCreate(entailment_ids=[first.id, second.id])
        )
        assert repo.get_multi_argument_coherence_dossier(dossier.id).id == dossier.id
        assert repo.list_multi_argument_coherence_dossiers()[0].id == dossier.id
        with pytest.raises(Exception, match="immutable"):
            with repo.connect() as connection:
                connection.execute(
                    "UPDATE multi_argument_coherence_dossiers SET qualification='CONTRADICTORY' WHERE id=?",
                    (dossier.id,),
                )


def test_multi_argument_missing_entailment_is_rejected():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        valid = make_entailment(repo, "existing", ["P"], "P")
        with pytest.raises(KeyError, match="entailment not found: missing"):
            repo.create_multi_argument_coherence_dossier(
                MultiArgumentCoherenceCreate(entailment_ids=[valid.id, "missing"])
            )


def make_stability_entailment(repo, premises, conclusion, name="policy", variables=None):
    argument = repo.create_argument(
        ArgumentCreate(
            name=name,
            premises=premises,
            conclusion=conclusion,
            variables=variables or ["P", "Q"],
        )
    )
    return repo.check_entailment(EntailmentCheckCreate(argument_id=argument.id))


def test_stability_series_is_server_ordered_and_stable():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["P", "Q"], "P")
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[second.id, first.id])
        )
        assert dossier.qualification == "STABLE"
        assert dossier.chronological_entailment_ids == [first.id, second.id]
        assert dossier.longest_stable_streak.length == 2
        assert dossier.transitions[0].kind == "STABLE"


def test_stability_detects_regression_and_counterexample():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["Q"], "P")
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[first.id, second.id])
        )
        assert dossier.qualification == "REGRESSED"
        assert dossier.regression_count == 1
        assert dossier.worst_transition.kind == "REGRESSION"
        assert dossier.worst_transition.witness == {"P": False, "Q": True}


def test_stability_detects_recovery_after_regression():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["Q"], "P")
        third = make_stability_entailment(repo, ["P & Q"], "P")
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[third.id, first.id, second.id])
        )
        assert dossier.qualification == "RECOVERED"
        assert dossier.regression_count == dossier.recovery_count == 1
        assert [item.kind for item in dossier.transitions] == ["REGRESSION", "RECOVERY"]
        assert dossier.worst_transition.kind == "REGRESSION"


def test_stability_inconsistent_premises_are_insufficient():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["P", "!P"], "Q")
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[first.id, second.id])
        )
        assert dossier.qualification == "INSUFFICIENT"
        assert dossier.transitions[0].kind == "INSUFFICIENT_CHANGE"
        assert dossier.entries[1].premise_models == 0


def test_stability_incompatible_series_names_are_rejected_prudently():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P", name="policy-a")
        second = make_stability_entailment(repo, ["P", "Q"], "P", name="policy-b")
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[first.id, second.id])
        )
        assert dossier.qualification == "INCOMPATIBLE"
        assert "incompatible_argument_names" in dossier.issues


def test_stability_recalculates_hashes_and_detects_corruption():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["P", "Q"], "P")
        with repo.connect() as connection:
            connection.execute("DROP TRIGGER entailments_no_update")
            connection.execute(
                "UPDATE entailment_checks SET entailment_hash=? WHERE id=?",
                ("0" * 64, first.id),
            )
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[first.id, second.id])
        )
        assert dossier.qualification == "INCOMPATIBLE"
        assert dossier.entries[0].verification_valid is False


def test_stability_recalculates_exact_dependencies():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["P", "P -> Q"], "Q")
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[first.id, second.id])
        )
        assert len(dossier.dependencies) == 1
        assert dossier.dependencies[0].provider_entailment_id == first.id
        assert dossier.dependencies[0].consumer_entailment_id == second.id
        assert dossier.dependencies[0].formula == "P"


def test_stability_snapshot_is_order_independent_idempotent_and_audited_once():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["P", "Q"], "P")
        created = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[second.id, first.id])
        )
        replay = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[first.id, second.id])
        )
        assert replay.id == created.id and replay.idempotent_replay is True
        assert len(created.snapshot_hash) == len(created.dossier_hash) == 64
        with repo.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE event_type='PROOF_STABILITY_ANALYZED'"
            ).fetchone()[0]
        assert count == 1


def test_stability_dossier_is_immutable_gettable_and_listed():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_stability_entailment(repo, ["P"], "P")
        second = make_stability_entailment(repo, ["P", "Q"], "P")
        dossier = repo.create_proof_stability_dossier(
            ProofStabilityDossierCreate(entailment_ids=[first.id, second.id])
        )
        assert repo.get_proof_stability_dossier(dossier.id).id == dossier.id
        assert repo.list_proof_stability_dossiers()[0].id == dossier.id
        with pytest.raises(Exception, match="immutable"):
            with repo.connect() as connection:
                connection.execute(
                    "UPDATE proof_stability_dossiers SET qualification='REGRESSED' WHERE id=?",
                    (dossier.id,),
                )


def test_stability_request_is_strict_bounded_and_missing_proof_is_rejected():
    invalid = [
        {"entailment_ids": ["one"]},
        {"entailment_ids": ["same", "same"]},
        {"entailment_ids": [str(index) for index in range(101)]},
        {"entailment_ids": ["one", "two"], "qualification": "STABLE"},
        {"entailment_ids": ["one", "two"], "transitions": []},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            ProofStabilityDossierCreate.model_validate(payload)
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        existing = make_stability_entailment(repo, ["P"], "P")
        with pytest.raises(KeyError, match="entailment not found: missing"):
            repo.create_proof_stability_dossier(
                ProofStabilityDossierCreate(entailment_ids=[existing.id, "missing"])
            )


def test_v107_stability_api_remains_aligned():
    root = Path(__file__).resolve().parents[1]
    static = yaml.safe_load((root / "packages/contracts/openapi.yaml").read_text())
    runtime = app.openapi()
    client = TestClient(app)
    assert client.get("/health").json()["version"] == "1.0.7"
    assert client.get("/info").json()["release"] == "V1.07"
    assert client.get("/v1/proof-dependency-dossiers/missing").status_code == 404
    assert static["openapi"] == runtime["openapi"] == "3.1.0"
    assert client.get("/v1/multi-argument-coherence-dossiers/missing").status_code == 404
    assert client.post(
        "/v1/multi-argument-coherence-dossiers",
        json={"entailment_ids": ["a", "b"], "qualification": "CONSISTENT"},
    ).status_code == 422
    assert client.post(
        "/v1/multi-argument-coherence-dossiers",
        json={"entailment_ids": ["a", "b"]},
    ).status_code == 404
    assert client.get("/v1/proof-stability-dossiers/missing").status_code == 404
    assert client.post(
        "/v1/proof-stability-dossiers",
        json={"entailment_ids": ["a", "b"], "qualification": "STABLE"},
    ).status_code == 422
    argument_one = client.post(
        "/v1/arguments",
        json={
            "name": "api-stability",
            "premises": ["P"],
            "conclusion": "P",
            "variables": ["P", "Q"],
        },
    ).json()
    argument_two = client.post(
        "/v1/arguments",
        json={
            "name": "api-stability",
            "premises": ["P", "Q"],
            "conclusion": "P",
            "variables": ["P", "Q"],
        },
    ).json()
    proof_one = client.post(
        "/v1/entailments", json={"argument_id": argument_one["id"]}
    ).json()
    proof_two = client.post(
        "/v1/entailments", json={"argument_id": argument_two["id"]}
    ).json()
    created = client.post(
        "/v1/proof-stability-dossiers",
        json={"entailment_ids": [proof_two["id"], proof_one["id"]]},
    )
    assert created.status_code == 201 and created.json()["qualification"] == "STABLE"
    dossier_id = created.json()["id"]
    assert client.get(f"/v1/proof-stability-dossiers/{dossier_id}").json()["id"] == dossier_id
    assert any(item["id"] == dossier_id for item in client.get("/v1/proof-stability-dossiers").json())
    assert static["info"]["version"] == runtime["info"]["version"] == "1.0.7"
    assert set(static["paths"]) == set(runtime["paths"])


def make_coverage_entailment(repo, name, premises, conclusion):
    argument = repo.create_argument(
        ArgumentCreate(
            name=name,
            premises=premises,
            conclusion=conclusion,
            variables=["P", "Q"],
        )
    )
    return repo.check_entailment(EntailmentCheckCreate(argument_id=argument.id))


def test_obligation_coverage_is_complete_with_distinct_verified_providers():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_coverage_entailment(repo, "p-one", ["P & P"], "P")
        second = make_coverage_entailment(repo, "p-two", ["P"], "P & P")
        dossier = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[second.id, first.id]
            )
        )
        assert dossier.qualification == "COMPLETE"
        assert dossier.coverage_ratio == 1
        assert dossier.covered_obligation_count == dossier.total_obligation_count == 2
        assert all(item.status == "COVERED" for item in dossier.obligations)
        assert all(
            item.consumer_entailment_id not in item.provider_entailment_ids
            for item in dossier.obligations
        )


def test_obligation_coverage_reports_exact_gaps_and_worst_reference():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        provider = make_coverage_entailment(repo, "provider", ["P"], "P")
        consumer = make_coverage_entailment(
            repo, "consumer", ["P", "P -> Q"], "Q"
        )
        dossier = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[consumer.id, provider.id]
            )
        )
        assert dossier.qualification == "GAPPED"
        assert dossier.total_obligation_count == 3
        assert dossier.covered_obligation_count == 1
        uncovered = [item for item in dossier.obligations if item.status == "UNCOVERED"]
        assert {item.formula for item in uncovered} == {"P", "P -> Q"}
        assert dossier.worst_reference.entailment_id == provider.id
        assert consumer.id in dossier.orphan_provider_entailment_ids


def test_obligation_coverage_is_insufficient_when_a_reference_is_not_entailed():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        valid = make_coverage_entailment(repo, "valid", ["P"], "P")
        invalid = make_coverage_entailment(repo, "invalid", ["Q"], "P")
        dossier = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[valid.id, invalid.id]
            )
        )
        assert invalid.verdict == "NOT_ENTAILED"
        assert dossier.qualification == "INSUFFICIENT"
        assert any(
            issue == f"provider_not_established:{invalid.id}:NOT_ENTAILED"
            for issue in dossier.issues
        )


def test_obligation_coverage_recomputes_and_detects_corrupted_evidence():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_coverage_entailment(repo, "integrity-one", ["P & P"], "P")
        second = make_coverage_entailment(repo, "integrity-two", ["P"], "P & P")
        with repo.connect() as connection:
            connection.execute("DROP TRIGGER entailments_no_update")
            connection.execute(
                "UPDATE entailment_checks SET entailment_hash=? WHERE id=?",
                ("0" * 64, first.id),
            )
        dossier = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[first.id, second.id]
            )
        )
        assert dossier.qualification == "INCOMPATIBLE"
        assert next(
            item for item in dossier.references if item.entailment_id == first.id
        ).verification_valid is False


def test_obligation_coverage_request_is_strict_unique_and_bounded():
    invalid = [
        {"entailment_ids": ["one"]},
        {"entailment_ids": ["same", "same"]},
        {"entailment_ids": [str(index) for index in range(101)]},
        {"entailment_ids": ["one", "two"], "qualification": "COMPLETE"},
        {"entailment_ids": ["one", "two"], "coverage_ratio": 1},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            ProofObligationCoverageDossierCreate.model_validate(payload)


def test_obligation_coverage_missing_reference_is_rejected():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        existing = make_coverage_entailment(repo, "existing", ["P"], "P")
        with pytest.raises(KeyError, match="entailment not found: missing"):
            repo.create_proof_obligation_coverage_dossier(
                ProofObligationCoverageDossierCreate(
                    entailment_ids=[existing.id, "missing"]
                )
            )


def test_obligation_coverage_is_order_independent_idempotent_and_audited_once():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_coverage_entailment(repo, "order-one", ["P & P"], "P")
        second = make_coverage_entailment(repo, "order-two", ["P"], "P & P")
        created = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[second.id, first.id]
            )
        )
        replay = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[first.id, second.id]
            )
        )
        assert replay.id == created.id and replay.idempotent_replay is True
        assert created.ordered_entailment_ids == [first.id, second.id]
        assert len(created.snapshot_hash) == len(created.dossier_hash) == 64
        with repo.connect() as connection:
            count = connection.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE event_type='PROOF_OBLIGATION_COVERAGE_ANALYZED'"""
            ).fetchone()[0]
        assert count == 1


def test_obligation_coverage_is_immutable_gettable_and_listed():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_coverage_entailment(repo, "immutable-one", ["P & P"], "P")
        second = make_coverage_entailment(repo, "immutable-two", ["P"], "P & P")
        dossier = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[first.id, second.id]
            )
        )
        assert repo.get_proof_obligation_coverage_dossier(dossier.id).id == dossier.id
        assert repo.list_proof_obligation_coverage_dossiers()[0].id == dossier.id
        with pytest.raises(Exception, match="immutable"):
            with repo.connect() as connection:
                connection.execute(
                    """UPDATE proof_obligation_coverage_dossiers
                       SET qualification='GAPPED' WHERE id=?""",
                    (dossier.id,),
                )


def test_obligation_provider_lists_are_deterministic_with_multiple_providers():
    with TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "proof.db")
        first = make_coverage_entailment(repo, "provider-one", ["P"], "P")
        second = make_coverage_entailment(repo, "provider-two", ["P", "P | Q"], "P")
        consumer = make_coverage_entailment(repo, "consumer", ["P"], "P | Q")
        dossier = repo.create_proof_obligation_coverage_dossier(
            ProofObligationCoverageDossierCreate(
                entailment_ids=[consumer.id, second.id, first.id]
            )
        )
        obligation = next(
            item
            for item in dossier.obligations
            if item.consumer_entailment_id == consumer.id
        )
        assert obligation.provider_entailment_ids == sorted([first.id, second.id])


def test_v107_obligation_coverage_api_and_openapi_are_aligned():
    root = Path(__file__).resolve().parents[1]
    client = TestClient(app)
    assert client.get("/health").json()["version"] == "1.0.7"
    assert client.get("/info").json()["release"] == "V1.07"
    assert client.get("/v1/proof-obligation-coverage-dossiers/missing").status_code == 404
    assert client.post(
        "/v1/proof-obligation-coverage-dossiers",
        json={"entailment_ids": ["a", "b"], "qualification": "COMPLETE"},
    ).status_code == 422
    assert client.post(
        "/v1/proof-obligation-coverage-dossiers",
        json={"entailment_ids": ["a", "b"]},
    ).status_code == 404
    argument_a = client.post(
        "/v1/arguments",
        json={
            "name": "api-coverage-a",
            "premises": ["P & P"],
            "conclusion": "P",
            "variables": ["P", "Q"],
        },
    ).json()
    argument_b = client.post(
        "/v1/arguments",
        json={
            "name": "api-coverage-b",
            "premises": ["P"],
            "conclusion": "P & P",
            "variables": ["P", "Q"],
        },
    ).json()
    proof_a = client.post(
        "/v1/entailments", json={"argument_id": argument_a["id"]}
    ).json()
    proof_b = client.post(
        "/v1/entailments", json={"argument_id": argument_b["id"]}
    ).json()
    created = client.post(
        "/v1/proof-obligation-coverage-dossiers",
        json={"entailment_ids": [proof_b["id"], proof_a["id"]]},
    )
    assert created.status_code == 201
    assert created.json()["qualification"] == "COMPLETE"
    dossier_id = created.json()["id"]
    assert client.get(
        f"/v1/proof-obligation-coverage-dossiers/{dossier_id}"
    ).json()["id"] == dossier_id
    assert any(
        item["id"] == dossier_id
        for item in client.get("/v1/proof-obligation-coverage-dossiers").json()
    )
    static = yaml.safe_load((root / "packages/contracts/openapi.yaml").read_text())
    runtime = app.openapi()
    assert static == runtime
