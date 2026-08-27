import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    Argument,
    ArgumentCreate,
    EntailmentCheck,
    EntailmentCheckCreate,
    FormulaComparison,
    FormulaComparisonCreate,
    InconsistencyAnalysis,
    InconsistencyAnalysisCreate,
    MultiArgumentCoherenceCreate,
    MultiArgumentCoherenceDossier,
    ProofStabilityDossier,
    ProofStabilityDossierCreate,
    ProofObligationCoverageDossier,
    ProofObligationCoverageDossierCreate,
    PremiseSet,
    PremiseSetCreate,
    ProofDependencyDossier,
    ProofDependencyDossierCreate,
    Proposition,
    PropositionCreate,
    Verification,
    VerificationCreate,
)
from .verifier import (
    analyze_inconsistency,
    canonical_hash,
    compare_formulas,
    verify,
    verify_argument,
)


SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS propositions(
 id TEXT PRIMARY KEY, proposition_hash TEXT NOT NULL UNIQUE,
 specification_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verifications(
 id TEXT PRIMARY KEY, proposition_id TEXT NOT NULL REFERENCES propositions(id),
 method TEXT NOT NULL, verdict TEXT NOT NULL CHECK(verdict IN ('VERIFIED','REFUTED')),
 valuations_checked INTEGER NOT NULL, counterexample_json TEXT,
 verification_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 UNIQUE(proposition_id,method)
);
CREATE TABLE IF NOT EXISTS arguments(
 id TEXT PRIMARY KEY, argument_hash TEXT NOT NULL UNIQUE,
 specification_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entailment_checks(
 id TEXT PRIMARY KEY, argument_id TEXT NOT NULL REFERENCES arguments(id),
 method TEXT NOT NULL,
 verdict TEXT NOT NULL CHECK(verdict IN ('ENTAILED','NOT_ENTAILED','INCONSISTENT_PREMISES')),
 valuations_checked INTEGER NOT NULL, premise_models INTEGER NOT NULL,
 counterexample_json TEXT, entailment_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, UNIQUE(argument_id,method)
);
CREATE TABLE IF NOT EXISTS formula_comparisons(
 id TEXT PRIMARY KEY, input_hash TEXT NOT NULL UNIQUE,
 specification_json TEXT NOT NULL,
 verdict TEXT NOT NULL CHECK(verdict IN ('EQUIVALENT','NOT_EQUIVALENT')),
 valuations_checked INTEGER NOT NULL, counterexample_json TEXT,
 comparison_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS premise_sets(
 id TEXT PRIMARY KEY, premise_set_hash TEXT NOT NULL UNIQUE,
 specification_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inconsistency_analyses(
 id TEXT PRIMARY KEY, premise_set_id TEXT NOT NULL REFERENCES premise_sets(id),
 method TEXT NOT NULL, verdict TEXT NOT NULL CHECK(verdict IN ('CONSISTENT','INCONSISTENT')),
 valuations_checked INTEGER NOT NULL, satisfying_assignment_json TEXT,
 core_indices_json TEXT NOT NULL, minimal_core_json TEXT NOT NULL,
 necessity_witnesses_json TEXT NOT NULL, minimality_verified INTEGER NOT NULL,
 analysis_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 UNIQUE(premise_set_id,method)
);
CREATE TABLE IF NOT EXISTS proof_dependency_dossiers(
 id TEXT PRIMARY KEY, root_entailment_id TEXT NOT NULL REFERENCES entailment_checks(id),
 method TEXT NOT NULL, input_hash TEXT NOT NULL UNIQUE,
 qualification TEXT NOT NULL CHECK(qualification IN ('CLOSED','OPEN_ASSUMPTIONS','CYCLIC','INVALID')),
 nodes_json TEXT NOT NULL, edges_json TEXT NOT NULL,
 reachable_ids_json TEXT NOT NULL, unused_ids_json TEXT NOT NULL,
 open_assumptions_json TEXT NOT NULL, cycles_json TEXT NOT NULL,
 evidence_hash TEXT NOT NULL, dossier_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS multi_argument_coherence_dossiers(
 id TEXT PRIMARY KEY, input_hash TEXT NOT NULL,
 entailment_ids_json TEXT NOT NULL, method TEXT NOT NULL,
 qualification TEXT NOT NULL CHECK(qualification IN ('CONSISTENT','CONTRADICTORY','INSUFFICIENT','INCOMPATIBLE')),
 variables_json TEXT NOT NULL, conclusions_json TEXT NOT NULL,
 proofs_json TEXT NOT NULL, witnesses_json TEXT NOT NULL,
 satisfying_assignment_json TEXT, issues_json TEXT NOT NULL,
 valuations_checked INTEGER NOT NULL CHECK(valuations_checked>=0),
 snapshot_hash TEXT NOT NULL, dossier_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL,
 UNIQUE(input_hash,snapshot_hash,method)
);
CREATE TABLE IF NOT EXISTS proof_stability_dossiers(
 id TEXT PRIMARY KEY, input_hash TEXT NOT NULL,
 entailment_ids_json TEXT NOT NULL, chronological_ids_json TEXT NOT NULL,
 method TEXT NOT NULL,
 qualification TEXT NOT NULL CHECK(qualification IN ('STABLE','REGRESSED','RECOVERED','INSUFFICIENT','INCOMPATIBLE')),
 entries_json TEXT NOT NULL, transitions_json TEXT NOT NULL,
 dependencies_json TEXT NOT NULL, regression_count INTEGER NOT NULL,
 recovery_count INTEGER NOT NULL, longest_streak_json TEXT NOT NULL,
 worst_transition_json TEXT NOT NULL, issues_json TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL, dossier_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, UNIQUE(input_hash,snapshot_hash,method)
);
CREATE TABLE IF NOT EXISTS proof_obligation_coverage_dossiers(
 id TEXT PRIMARY KEY, input_hash TEXT NOT NULL,
 entailment_ids_json TEXT NOT NULL, ordered_ids_json TEXT NOT NULL,
 method TEXT NOT NULL,
 qualification TEXT NOT NULL CHECK(qualification IN ('COMPLETE','GAPPED','INSUFFICIENT','INCOMPATIBLE')),
 references_json TEXT NOT NULL, obligations_json TEXT NOT NULL,
 total_obligation_count INTEGER NOT NULL CHECK(total_obligation_count>=0),
 covered_obligation_count INTEGER NOT NULL CHECK(covered_obligation_count>=0),
 uncovered_obligation_count INTEGER NOT NULL CHECK(uncovered_obligation_count>=0),
 coverage_ratio REAL NOT NULL CHECK(coverage_ratio>=0 AND coverage_ratio<=1),
 orphan_provider_ids_json TEXT NOT NULL, worst_reference_json TEXT NOT NULL,
 issues_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
 dossier_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 UNIQUE(input_hash,snapshot_hash,method)
);
CREATE TABLE IF NOT EXISTS audit_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,
 entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS propositions_no_update BEFORE UPDATE ON propositions BEGIN SELECT RAISE(ABORT,'propositions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS propositions_no_delete BEFORE DELETE ON propositions BEGIN SELECT RAISE(ABORT,'propositions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS verifications_no_update BEFORE UPDATE ON verifications BEGIN SELECT RAISE(ABORT,'verifications are immutable'); END;
CREATE TRIGGER IF NOT EXISTS verifications_no_delete BEFORE DELETE ON verifications BEGIN SELECT RAISE(ABORT,'verifications are immutable'); END;
CREATE TRIGGER IF NOT EXISTS arguments_no_update BEFORE UPDATE ON arguments BEGIN SELECT RAISE(ABORT,'arguments are immutable'); END;
CREATE TRIGGER IF NOT EXISTS arguments_no_delete BEFORE DELETE ON arguments BEGIN SELECT RAISE(ABORT,'arguments are immutable'); END;
CREATE TRIGGER IF NOT EXISTS entailments_no_update BEFORE UPDATE ON entailment_checks BEGIN SELECT RAISE(ABORT,'entailment checks are immutable'); END;
CREATE TRIGGER IF NOT EXISTS entailments_no_delete BEFORE DELETE ON entailment_checks BEGIN SELECT RAISE(ABORT,'entailment checks are immutable'); END;
CREATE TRIGGER IF NOT EXISTS comparisons_no_update BEFORE UPDATE ON formula_comparisons BEGIN SELECT RAISE(ABORT,'formula comparisons are immutable'); END;
CREATE TRIGGER IF NOT EXISTS comparisons_no_delete BEFORE DELETE ON formula_comparisons BEGIN SELECT RAISE(ABORT,'formula comparisons are immutable'); END;
CREATE TRIGGER IF NOT EXISTS premise_sets_no_update BEFORE UPDATE ON premise_sets BEGIN SELECT RAISE(ABORT,'premise sets are immutable'); END;
CREATE TRIGGER IF NOT EXISTS premise_sets_no_delete BEFORE DELETE ON premise_sets BEGIN SELECT RAISE(ABORT,'premise sets are immutable'); END;
CREATE TRIGGER IF NOT EXISTS inconsistency_analyses_no_update BEFORE UPDATE ON inconsistency_analyses BEGIN SELECT RAISE(ABORT,'inconsistency analyses are immutable'); END;
CREATE TRIGGER IF NOT EXISTS inconsistency_analyses_no_delete BEFORE DELETE ON inconsistency_analyses BEGIN SELECT RAISE(ABORT,'inconsistency analyses are immutable'); END;
CREATE TRIGGER IF NOT EXISTS proof_dependency_dossiers_no_update BEFORE UPDATE ON proof_dependency_dossiers BEGIN SELECT RAISE(ABORT,'proof dependency dossiers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS proof_dependency_dossiers_no_delete BEFORE DELETE ON proof_dependency_dossiers BEGIN SELECT RAISE(ABORT,'proof dependency dossiers are immutable'); END;
CREATE INDEX IF NOT EXISTS coherence_dossiers_input ON multi_argument_coherence_dossiers(input_hash,created_at);
CREATE TRIGGER IF NOT EXISTS coherence_dossiers_no_update BEFORE UPDATE ON multi_argument_coherence_dossiers BEGIN SELECT RAISE(ABORT,'multi-argument coherence dossiers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS coherence_dossiers_no_delete BEFORE DELETE ON multi_argument_coherence_dossiers BEGIN SELECT RAISE(ABORT,'multi-argument coherence dossiers are immutable'); END;
CREATE INDEX IF NOT EXISTS stability_dossiers_input ON proof_stability_dossiers(input_hash,created_at);
CREATE TRIGGER IF NOT EXISTS stability_dossiers_no_update BEFORE UPDATE ON proof_stability_dossiers BEGIN SELECT RAISE(ABORT,'proof stability dossiers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS stability_dossiers_no_delete BEFORE DELETE ON proof_stability_dossiers BEGIN SELECT RAISE(ABORT,'proof stability dossiers are immutable'); END;
CREATE INDEX IF NOT EXISTS obligation_coverage_dossiers_input ON proof_obligation_coverage_dossiers(input_hash,created_at);
CREATE TRIGGER IF NOT EXISTS obligation_coverage_dossiers_no_update BEFORE UPDATE ON proof_obligation_coverage_dossiers BEGIN SELECT RAISE(ABORT,'proof obligation coverage dossiers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS obligation_coverage_dossiers_no_delete BEFORE DELETE ON proof_obligation_coverage_dossiers BEGIN SELECT RAISE(ABORT,'proof obligation coverage dossiers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END;
"""


def now(): return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self,path: str | Path): self.path=str(path); self.initialize()

    @contextmanager
    def connect(self):
        connection=sqlite3.connect(self.path); connection.row_factory=sqlite3.Row; connection.execute("PRAGMA foreign_keys=ON")
        try: yield connection; connection.commit()
        finally: connection.close()

    def initialize(self):
        with self.connect() as connection: connection.executescript(SCHEMA)

    def audit(self,connection,event,kind,entity_id,payload):
        connection.execute("INSERT INTO audit_events(event_type,entity_type,entity_id,payload_json,created_at) VALUES(?,?,?,?,?)",(event,kind,entity_id,json.dumps(payload,sort_keys=True),now()))

    def create_proposition(self,data: PropositionCreate) -> Proposition:
        proposition_hash=canonical_hash(data.model_dump(mode="json")); created=now(); pid=str(uuid.uuid4())
        with self.connect() as connection:
            existing=connection.execute("SELECT * FROM propositions WHERE proposition_hash=?",(proposition_hash,)).fetchone()
            if existing: return self.proposition(existing)
            connection.execute("INSERT INTO propositions VALUES(?,?,?,?)",(pid,proposition_hash,data.model_dump_json(),created))
            self.audit(connection,"PROPOSITION_FROZEN","proposition",pid,{"proposition_hash":proposition_hash})
        return Proposition(id=pid,proposition_hash=proposition_hash,specification=data,created_at=created)

    def proposition(self,row):
        return Proposition(id=row["id"],proposition_hash=row["proposition_hash"],specification=PropositionCreate.model_validate_json(row["specification_json"]),created_at=row["created_at"])

    def list_propositions(self):
        with self.connect() as connection: rows=connection.execute("SELECT * FROM propositions ORDER BY created_at DESC").fetchall()
        return [self.proposition(row) for row in rows]

    def verify(self,data: VerificationCreate) -> Verification:
        with self.connect() as connection:
            proposition=connection.execute("SELECT * FROM propositions WHERE id=?",(data.proposition_id,)).fetchone()
            if not proposition: raise KeyError("proposition not found")
            existing=connection.execute("SELECT * FROM verifications WHERE proposition_id=? AND method=?",(data.proposition_id,data.method)).fetchone()
        if existing: return self.verification(existing,True)
        specification=PropositionCreate.model_validate_json(proposition["specification_json"])
        verdict,checked,counterexample,result_hash=verify(specification.formal_expression,specification.variables)
        vid=str(uuid.uuid4()); created=now()
        with self.connect() as connection:
            connection.execute("INSERT INTO verifications VALUES(?,?,?,?,?,?,?,?)",(vid,data.proposition_id,data.method,verdict,checked,json.dumps(counterexample) if counterexample is not None else None,result_hash,created))
            self.audit(connection,"PROPOSITION_VERIFIED","verification",vid,{"verdict":verdict,"verification_hash":result_hash})
            row=connection.execute("SELECT * FROM verifications WHERE id=?",(vid,)).fetchone()
        return self.verification(row)

    def verification(self,row,idempotent=False):
        return Verification(id=row["id"],proposition_id=row["proposition_id"],method=row["method"],verdict=row["verdict"],valuations_checked=row["valuations_checked"],counterexample=json.loads(row["counterexample_json"]) if row["counterexample_json"] else None,verification_hash=row["verification_hash"],reproducible=True,idempotent_replay=idempotent,created_at=row["created_at"])

    def create_argument(self, data: ArgumentCreate) -> Argument:
        argument_hash = canonical_hash(data.model_dump(mode="json"))
        created = now()
        argument_id = str(uuid.uuid4())
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM arguments WHERE argument_hash=?", (argument_hash,)
            ).fetchone()
            if existing:
                return self.argument(existing)
            connection.execute(
                "INSERT INTO arguments VALUES(?,?,?,?)",
                (argument_id, argument_hash, data.model_dump_json(), created),
            )
            self.audit(
                connection,
                "ARGUMENT_FROZEN",
                "argument",
                argument_id,
                {"argument_hash": argument_hash},
            )
        return Argument(
            id=argument_id,
            argument_hash=argument_hash,
            specification=data,
            created_at=created,
        )

    def argument(self, row) -> Argument:
        return Argument(
            id=row["id"],
            argument_hash=row["argument_hash"],
            specification=ArgumentCreate.model_validate_json(row["specification_json"]),
            created_at=row["created_at"],
        )

    def list_arguments(self) -> list[Argument]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM arguments ORDER BY created_at DESC"
            ).fetchall()
        return [self.argument(row) for row in rows]

    def check_entailment(self, data: EntailmentCheckCreate) -> EntailmentCheck:
        with self.connect() as connection:
            argument = connection.execute(
                "SELECT * FROM arguments WHERE id=?", (data.argument_id,)
            ).fetchone()
            if not argument:
                raise KeyError("argument not found")
            existing = connection.execute(
                "SELECT * FROM entailment_checks WHERE argument_id=? AND method=?",
                (data.argument_id, data.method),
            ).fetchone()
        if existing:
            return self.entailment(existing, True)

        specification = ArgumentCreate.model_validate_json(argument["specification_json"])
        verdict, checked, premise_models, counterexample, result_hash = verify_argument(
            specification.premises,
            specification.conclusion,
            specification.variables,
        )
        check_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO entailment_checks VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    check_id,
                    data.argument_id,
                    data.method,
                    verdict,
                    checked,
                    premise_models,
                    json.dumps(counterexample) if counterexample is not None else None,
                    result_hash,
                    created,
                ),
            )
            self.audit(
                connection,
                "ARGUMENT_CHECKED",
                "entailment_check",
                check_id,
                {"verdict": verdict, "entailment_hash": result_hash},
            )
            row = connection.execute(
                "SELECT * FROM entailment_checks WHERE id=?", (check_id,)
            ).fetchone()
        return self.entailment(row)

    def entailment(self, row, idempotent: bool = False) -> EntailmentCheck:
        return EntailmentCheck(
            id=row["id"],
            argument_id=row["argument_id"],
            method=row["method"],
            verdict=row["verdict"],
            valuations_checked=row["valuations_checked"],
            premise_models=row["premise_models"],
            counterexample=json.loads(row["counterexample_json"])
            if row["counterexample_json"]
            else None,
            entailment_hash=row["entailment_hash"],
            idempotent_replay=idempotent,
            created_at=row["created_at"],
        )

    def compare(self, data: FormulaComparisonCreate) -> FormulaComparison:
        input_hash = canonical_hash(data.model_dump(mode="json"))
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM formula_comparisons WHERE input_hash=?", (input_hash,)
            ).fetchone()
        if existing:
            return self.formula_comparison(existing, True)

        verdict, checked, counterexample, comparison_hash = compare_formulas(
            data.left_expression, data.right_expression, data.variables
        )
        comparison_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO formula_comparisons VALUES(?,?,?,?,?,?,?,?)",
                (
                    comparison_id,
                    input_hash,
                    data.model_dump_json(),
                    verdict,
                    checked,
                    json.dumps(counterexample) if counterexample is not None else None,
                    comparison_hash,
                    created,
                ),
            )
            self.audit(
                connection,
                "FORMULAS_COMPARED",
                "formula_comparison",
                comparison_id,
                {"verdict": verdict, "comparison_hash": comparison_hash},
            )
            row = connection.execute(
                "SELECT * FROM formula_comparisons WHERE id=?", (comparison_id,)
            ).fetchone()
        return self.formula_comparison(row)

    def formula_comparison(
        self, row, idempotent: bool = False
    ) -> FormulaComparison:
        return FormulaComparison(
            id=row["id"],
            input_hash=row["input_hash"],
            specification=FormulaComparisonCreate.model_validate_json(
                row["specification_json"]
            ),
            verdict=row["verdict"],
            valuations_checked=row["valuations_checked"],
            counterexample=json.loads(row["counterexample_json"])
            if row["counterexample_json"]
            else None,
            comparison_hash=row["comparison_hash"],
            idempotent_replay=idempotent,
            created_at=row["created_at"],
        )

    def list_formula_comparisons(self) -> list[FormulaComparison]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM formula_comparisons ORDER BY created_at DESC"
            ).fetchall()
        return [self.formula_comparison(row) for row in rows]

    def get_formula_comparison(self, comparison_id: str) -> FormulaComparison:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM formula_comparisons WHERE id=?", (comparison_id,)
            ).fetchone()
        if not row:
            raise KeyError("formula comparison not found")
        return self.formula_comparison(row)

    def create_premise_set(self, data: PremiseSetCreate) -> PremiseSet:
        premise_set_hash = canonical_hash(data.model_dump(mode="json"))
        premise_set_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM premise_sets WHERE premise_set_hash=?",
                (premise_set_hash,),
            ).fetchone()
            if existing:
                return self.premise_set(existing)
            connection.execute(
                "INSERT INTO premise_sets VALUES(?,?,?,?)",
                (premise_set_id, premise_set_hash, data.model_dump_json(), created),
            )
            self.audit(
                connection,
                "PREMISE_SET_FROZEN",
                "premise_set",
                premise_set_id,
                {"premise_set_hash": premise_set_hash},
            )
        return PremiseSet(
            id=premise_set_id,
            premise_set_hash=premise_set_hash,
            specification=data,
            created_at=created,
        )

    def premise_set(self, row) -> PremiseSet:
        return PremiseSet(
            id=row["id"],
            premise_set_hash=row["premise_set_hash"],
            specification=PremiseSetCreate.model_validate_json(row["specification_json"]),
            created_at=row["created_at"],
        )

    def list_premise_sets(self) -> list[PremiseSet]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM premise_sets ORDER BY created_at DESC"
            ).fetchall()
        return [self.premise_set(row) for row in rows]

    def analyze_premise_set(
        self, data: InconsistencyAnalysisCreate
    ) -> InconsistencyAnalysis:
        with self.connect() as connection:
            premise_set_row = connection.execute(
                "SELECT * FROM premise_sets WHERE id=?", (data.premise_set_id,)
            ).fetchone()
            if not premise_set_row:
                raise KeyError("premise set not found")
            existing = connection.execute(
                "SELECT * FROM inconsistency_analyses WHERE premise_set_id=? AND method=?",
                (data.premise_set_id, data.method),
            ).fetchone()
        if existing:
            return self.inconsistency_analysis(existing, True)

        specification = PremiseSetCreate.model_validate_json(
            premise_set_row["specification_json"]
        )
        result = analyze_inconsistency(
            specification.premises, specification.variables
        )
        analysis_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO inconsistency_analyses VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    analysis_id,
                    data.premise_set_id,
                    data.method,
                    result["verdict"],
                    result["valuations_checked"],
                    json.dumps(result["satisfying_assignment"])
                    if result["satisfying_assignment"] is not None
                    else None,
                    json.dumps(result["core_indices"]),
                    json.dumps(result["minimal_core"]),
                    json.dumps(result["necessity_witnesses"], sort_keys=True),
                    int(result["minimality_verified"]),
                    result["analysis_hash"],
                    created,
                ),
            )
            self.audit(
                connection,
                "PREMISE_SET_ANALYZED",
                "inconsistency_analysis",
                analysis_id,
                {
                    "verdict": result["verdict"],
                    "analysis_hash": result["analysis_hash"],
                    "core_size": len(result["minimal_core"]),
                },
            )
            row = connection.execute(
                "SELECT * FROM inconsistency_analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        return self.inconsistency_analysis(row)

    def inconsistency_analysis(
        self, row, idempotent: bool = False
    ) -> InconsistencyAnalysis:
        return InconsistencyAnalysis(
            id=row["id"],
            premise_set_id=row["premise_set_id"],
            method=row["method"],
            verdict=row["verdict"],
            valuations_checked=row["valuations_checked"],
            satisfying_assignment=json.loads(row["satisfying_assignment_json"])
            if row["satisfying_assignment_json"]
            else None,
            core_indices=json.loads(row["core_indices_json"]),
            minimal_core=json.loads(row["minimal_core_json"]),
            necessity_witnesses=json.loads(row["necessity_witnesses_json"]),
            minimality_verified=bool(row["minimality_verified"]),
            analysis_hash=row["analysis_hash"],
            idempotent_replay=idempotent,
            created_at=row["created_at"],
        )

    def get_inconsistency_analysis(self, analysis_id: str) -> InconsistencyAnalysis:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM inconsistency_analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        if not row:
            raise KeyError("inconsistency analysis not found")
        return self.inconsistency_analysis(row)

    def create_proof_dependency_dossier(
        self, data: ProofDependencyDossierCreate
    ) -> ProofDependencyDossier:
        ordered_ids = [data.root_entailment_id] + sorted(data.supporting_entailment_ids)
        input_hash = canonical_hash(
            {"entailment_ids": ordered_ids, "method": data.method}
        )
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM proof_dependency_dossiers WHERE input_hash=?",
                (input_hash,),
            ).fetchone()
            if existing:
                return self.proof_dependency_dossier(existing, True)
            placeholders = ",".join("?" for _ in ordered_ids)
            rows = connection.execute(
                f"""SELECT e.*, a.argument_hash, a.specification_json
                    FROM entailment_checks e JOIN arguments a ON a.id=e.argument_id
                    WHERE e.id IN ({placeholders})""",
                ordered_ids,
            ).fetchall()
        if len(rows) != len(ordered_ids):
            found = {row["id"] for row in rows}
            missing = next(item for item in ordered_ids if item not in found)
            raise KeyError(f"entailment not found: {missing}")

        by_id = {row["id"]: row for row in rows}
        nodes = []
        evidence = []
        valid = True
        for entailment_id in ordered_ids:
            row = by_id[entailment_id]
            specification = ArgumentCreate.model_validate_json(row["specification_json"])
            verdict, checked, premise_models, counterexample, result_hash = verify_argument(
                specification.premises,
                specification.conclusion,
                specification.variables,
            )
            argument_hash = canonical_hash(specification.model_dump(mode="json"))
            verification_valid = (
                verdict == row["verdict"]
                and checked == row["valuations_checked"]
                and premise_models == row["premise_models"]
                and counterexample
                == (json.loads(row["counterexample_json"]) if row["counterexample_json"] else None)
                and result_hash == row["entailment_hash"]
                and argument_hash == row["argument_hash"]
            )
            valid = valid and verification_valid and verdict == "ENTAILED"
            nodes.append(
                {
                    "entailment_id": entailment_id,
                    "argument_id": row["argument_id"],
                    "conclusion": specification.conclusion,
                    "premises": specification.premises,
                    "verdict": verdict,
                    "verification_valid": verification_valid,
                }
            )
            evidence.append(
                {
                    "entailment_id": entailment_id,
                    "argument_hash": argument_hash,
                    "entailment_hash": result_hash,
                    "verdict": verdict,
                    "verification_valid": verification_valid,
                }
            )

        def formula_key(value: str) -> str:
            return "".join(value.split())

        providers: dict[str, list[str]] = {}
        for node in nodes:
            providers.setdefault(formula_key(node["conclusion"]), []).append(
                node["entailment_id"]
            )
        edges = []
        dependency_graph: dict[str, list[str]] = {item: [] for item in ordered_ids}
        for consumer in nodes:
            for premise in consumer["premises"]:
                for provider in sorted(providers.get(formula_key(premise), [])):
                    if provider == consumer["entailment_id"]:
                        continue
                    edges.append(
                        {
                            "provider_entailment_id": provider,
                            "consumer_entailment_id": consumer["entailment_id"],
                            "formula": premise,
                        }
                    )
                    dependency_graph[consumer["entailment_id"]].append(provider)
        edges.sort(
            key=lambda item: (
                item["consumer_entailment_id"],
                item["provider_entailment_id"],
                item["formula"],
            )
        )

        reachable: set[str] = set()
        cycles: list[list[str]] = []

        def visit(node_id: str, stack: list[str]) -> None:
            reachable.add(node_id)
            if node_id in stack:
                cycle = stack[stack.index(node_id) :] + [node_id]
                if cycle not in cycles:
                    cycles.append(cycle)
                return
            for provider_id in sorted(set(dependency_graph[node_id])):
                visit(provider_id, stack + [node_id])

        visit(data.root_entailment_id, [])
        root_node = next(
            node for node in nodes if node["entailment_id"] == data.root_entailment_id
        )
        open_assumptions = sorted(
            {
                premise
                for premise in root_node["premises"]
                if not any(
                    provider != data.root_entailment_id
                    for provider in providers.get(formula_key(premise), [])
                )
            },
            key=formula_key,
        )
        if not valid:
            qualification = "INVALID"
        elif cycles:
            qualification = "CYCLIC"
        elif open_assumptions:
            qualification = "OPEN_ASSUMPTIONS"
        else:
            qualification = "CLOSED"
        reachable_ids = sorted(reachable)
        unused_ids = sorted(set(ordered_ids) - reachable)
        evidence_hash = canonical_hash(evidence)
        result_payload = {
            "root_entailment_id": data.root_entailment_id,
            "method": data.method,
            "qualification": qualification,
            "nodes": nodes,
            "edges": edges,
            "reachable_entailment_ids": reachable_ids,
            "unused_entailment_ids": unused_ids,
            "open_assumptions": open_assumptions,
            "cycles": cycles,
            "evidence_hash": evidence_hash,
        }
        dossier_hash = canonical_hash(result_payload)
        dossier_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO proof_dependency_dossiers VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    dossier_id,
                    data.root_entailment_id,
                    data.method,
                    input_hash,
                    qualification,
                    json.dumps(nodes, sort_keys=True),
                    json.dumps(edges, sort_keys=True),
                    json.dumps(reachable_ids),
                    json.dumps(unused_ids),
                    json.dumps(open_assumptions),
                    json.dumps(cycles),
                    evidence_hash,
                    dossier_hash,
                    created,
                ),
            )
            self.audit(
                connection,
                "PROOF_DEPENDENCIES_ANALYZED",
                "proof_dependency_dossier",
                dossier_id,
                {"qualification": qualification, "dossier_hash": dossier_hash},
            )
            row = connection.execute(
                "SELECT * FROM proof_dependency_dossiers WHERE id=?", (dossier_id,)
            ).fetchone()
        return self.proof_dependency_dossier(row)

    def proof_dependency_dossier(
        self, row, idempotent: bool = False
    ) -> ProofDependencyDossier:
        return ProofDependencyDossier(
            id=row["id"],
            root_entailment_id=row["root_entailment_id"],
            method=row["method"],
            qualification=row["qualification"],
            nodes=json.loads(row["nodes_json"]),
            edges=json.loads(row["edges_json"]),
            reachable_entailment_ids=json.loads(row["reachable_ids_json"]),
            unused_entailment_ids=json.loads(row["unused_ids_json"]),
            open_assumptions=json.loads(row["open_assumptions_json"]),
            cycles=json.loads(row["cycles_json"]),
            evidence_hash=row["evidence_hash"],
            dossier_hash=row["dossier_hash"],
            idempotent_replay=idempotent,
            created_at=row["created_at"],
        )

    def get_proof_dependency_dossier(self, dossier_id: str) -> ProofDependencyDossier:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM proof_dependency_dossiers WHERE id=?", (dossier_id,)
            ).fetchone()
        if not row:
            raise KeyError("proof dependency dossier not found")
        return self.proof_dependency_dossier(row)

    def list_proof_dependency_dossiers(self) -> list[ProofDependencyDossier]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM proof_dependency_dossiers ORDER BY created_at DESC"
            ).fetchall()
        return [self.proof_dependency_dossier(row) for row in rows]

    def create_multi_argument_coherence_dossier(
        self, data: MultiArgumentCoherenceCreate
    ) -> MultiArgumentCoherenceDossier:
        """Recompute proofs and decide joint formal consistency server-side."""
        ordered_ids = sorted(data.entailment_ids)
        input_hash = canonical_hash(
            {"entailment_ids": ordered_ids, "method": data.method}
        )
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in ordered_ids)
            rows = connection.execute(
                f"""SELECT e.*, a.argument_hash, a.specification_json
                    FROM entailment_checks e JOIN arguments a ON a.id=e.argument_id
                    WHERE e.id IN ({placeholders})""",
                ordered_ids,
            ).fetchall()
        if len(rows) != len(ordered_ids):
            found = {row["id"] for row in rows}
            missing = next(item for item in ordered_ids if item not in found)
            raise KeyError(f"entailment not found: {missing}")

        by_id = {row["id"]: row for row in rows}
        proofs = []
        snapshot_proofs = []
        issues: list[str] = []
        variables: set[str] = set()
        languages: set[str] = set()
        entailment_methods: set[str] = set()
        conclusion_providers: dict[str, list[str]] = {}

        def formula_key(expression: str) -> str:
            return "".join(expression.split())

        for entailment_id in ordered_ids:
            row = by_id[entailment_id]
            specification = ArgumentCreate.model_validate_json(row["specification_json"])
            verdict, checked, premise_models, counterexample, computed_entailment_hash = verify_argument(
                specification.premises,
                specification.conclusion,
                specification.variables,
            )
            computed_argument_hash = canonical_hash(specification.model_dump(mode="json"))
            stored_counterexample = (
                json.loads(row["counterexample_json"])
                if row["counterexample_json"]
                else None
            )
            verification_valid = (
                computed_argument_hash == row["argument_hash"]
                and computed_entailment_hash == row["entailment_hash"]
                and verdict == row["verdict"]
                and checked == row["valuations_checked"]
                and premise_models == row["premise_models"]
                and counterexample == stored_counterexample
            )
            if not verification_valid:
                issues.append(f"proof_integrity_invalid:{entailment_id}")
            if verdict != "ENTAILED":
                issues.append(f"conclusion_not_established:{entailment_id}:{verdict}")
            variables.update(specification.variables)
            languages.add(specification.language)
            entailment_methods.add(row["method"])
            conclusion = formula_key(specification.conclusion)
            conclusion_providers.setdefault(conclusion, []).append(entailment_id)
            proofs.append(
                {
                    "entailment_id": entailment_id,
                    "argument_id": row["argument_id"],
                    "conclusion": specification.conclusion,
                    "variables": sorted(specification.variables),
                    "verdict": verdict,
                    "verification_valid": verification_valid,
                    "argument_hash": computed_argument_hash,
                    "entailment_hash": computed_entailment_hash,
                }
            )
            snapshot_proofs.append(
                {
                    "entailment_id": entailment_id,
                    "argument_id": row["argument_id"],
                    "stored_argument_hash": row["argument_hash"],
                    "computed_argument_hash": computed_argument_hash,
                    "stored_entailment_hash": row["entailment_hash"],
                    "computed_entailment_hash": computed_entailment_hash,
                    "stored_verdict": row["verdict"],
                    "computed_verdict": verdict,
                    "verification_valid": verification_valid,
                }
            )

        canonical_conclusions = sorted(conclusion_providers)
        ordered_variables = sorted(variables)
        incompatibilities = []
        if languages != {"propositional-v1"}:
            incompatibilities.append("incompatible_languages")
        if entailment_methods != {"truth-table-entailment-v1"}:
            incompatibilities.append("incompatible_entailment_methods")
        if len(ordered_variables) > 8:
            incompatibilities.append("combined_variable_limit_exceeded:8")
        issues = sorted(incompatibilities + issues)
        snapshot_hash = canonical_hash(
            {
                "entailment_ids": ordered_ids,
                "proofs": snapshot_proofs,
                "variables": ordered_variables,
                "canonical_conclusions": canonical_conclusions,
            }
        )
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT * FROM multi_argument_coherence_dossiers
                   WHERE input_hash=? AND snapshot_hash=? AND method=?""",
                (input_hash, snapshot_hash, data.method),
            ).fetchone()
        if existing:
            return self.multi_argument_coherence_dossier(existing, True)

        contradiction_witnesses = []
        satisfying_assignment = None
        valuations_checked = 0
        if incompatibilities:
            qualification = "INCOMPATIBLE"
        elif any(not proof["verification_valid"] or proof["verdict"] != "ENTAILED" for proof in proofs):
            qualification = "INSUFFICIENT"
        else:
            consistency = analyze_inconsistency(
                canonical_conclusions, ordered_variables
            )
            valuations_checked = consistency["valuations_checked"]
            satisfying_assignment = consistency["satisfying_assignment"]
            if consistency["verdict"] == "CONSISTENT":
                qualification = "CONSISTENT"
            else:
                qualification = "CONTRADICTORY"
                core_indices = consistency["core_indices"]
                core_conclusions = [canonical_conclusions[index] for index in core_indices]
                core_ids = sorted(
                    {
                        entailment_id
                        for conclusion in core_conclusions
                        for entailment_id in conclusion_providers[conclusion]
                    }
                )
                necessity_witnesses = []
                for witness in consistency["necessity_witnesses"]:
                    conclusion = canonical_conclusions[witness["removed_index"]]
                    necessity_witnesses.append(
                        {
                            "entailment_ids": sorted(conclusion_providers[conclusion]),
                            "conclusion": conclusion,
                            "valuation": witness["valuation"],
                        }
                    )
                contradiction_witnesses.append(
                    {
                        "kind": (
                            "LOGICAL_NEGATION_OR_INCOMPATIBILITY"
                            if len(core_conclusions) == 2
                            else "JOINT_IMPOSSIBILITY"
                        ),
                        "entailment_ids": core_ids,
                        "conclusions": core_conclusions,
                        "necessity_witnesses": necessity_witnesses,
                    }
                )

        payload = {
            "entailment_ids": ordered_ids,
            "method": data.method,
            "qualification": qualification,
            "variables": ordered_variables,
            "canonical_conclusions": canonical_conclusions,
            "proofs": proofs,
            "contradiction_witnesses": contradiction_witnesses,
            "satisfying_assignment": satisfying_assignment,
            "issues": issues,
            "valuations_checked": valuations_checked,
            "snapshot_hash": snapshot_hash,
        }
        dossier_hash = canonical_hash(payload)
        dossier_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO multi_argument_coherence_dossiers
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    dossier_id,
                    input_hash,
                    json.dumps(ordered_ids),
                    data.method,
                    qualification,
                    json.dumps(ordered_variables),
                    json.dumps(canonical_conclusions),
                    json.dumps(proofs, sort_keys=True),
                    json.dumps(contradiction_witnesses, sort_keys=True),
                    json.dumps(satisfying_assignment, sort_keys=True)
                    if satisfying_assignment is not None
                    else None,
                    json.dumps(issues),
                    valuations_checked,
                    snapshot_hash,
                    dossier_hash,
                    created,
                ),
            )
            self.audit(
                connection,
                "MULTI_ARGUMENT_COHERENCE_ANALYZED",
                "multi_argument_coherence_dossier",
                dossier_id,
                {
                    "qualification": qualification,
                    "snapshot_hash": snapshot_hash,
                    "dossier_hash": dossier_hash,
                },
            )
            row = connection.execute(
                "SELECT * FROM multi_argument_coherence_dossiers WHERE id=?",
                (dossier_id,),
            ).fetchone()
        return self.multi_argument_coherence_dossier(row)

    def multi_argument_coherence_dossier(
        self, row, idempotent: bool = False
    ) -> MultiArgumentCoherenceDossier:
        return MultiArgumentCoherenceDossier(
            id=row["id"],
            entailment_ids=json.loads(row["entailment_ids_json"]),
            method=row["method"],
            qualification=row["qualification"],
            variables=json.loads(row["variables_json"]),
            canonical_conclusions=json.loads(row["conclusions_json"]),
            proofs=json.loads(row["proofs_json"]),
            contradiction_witnesses=json.loads(row["witnesses_json"]),
            satisfying_assignment=json.loads(row["satisfying_assignment_json"])
            if row["satisfying_assignment_json"]
            else None,
            issues=json.loads(row["issues_json"]),
            valuations_checked=row["valuations_checked"],
            snapshot_hash=row["snapshot_hash"],
            dossier_hash=row["dossier_hash"],
            idempotent_replay=idempotent,
            created_at=row["created_at"],
        )

    def get_multi_argument_coherence_dossier(
        self, dossier_id: str
    ) -> MultiArgumentCoherenceDossier:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM multi_argument_coherence_dossiers WHERE id=?",
                (dossier_id,),
            ).fetchone()
        if not row:
            raise KeyError("multi-argument coherence dossier not found")
        return self.multi_argument_coherence_dossier(row)

    def list_multi_argument_coherence_dossiers(
        self,
    ) -> list[MultiArgumentCoherenceDossier]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM multi_argument_coherence_dossiers
                   ORDER BY created_at DESC, rowid DESC"""
            ).fetchall()
        return [self.multi_argument_coherence_dossier(row) for row in rows]

    def create_proof_stability_dossier(
        self, data: ProofStabilityDossierCreate
    ) -> ProofStabilityDossier:
        requested_ids = sorted(data.entailment_ids)
        input_hash = canonical_hash(
            {"entailment_ids": requested_ids, "method": data.method}
        )
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in requested_ids)
            rows = connection.execute(
                f"""SELECT e.*,a.argument_hash,a.specification_json
                    FROM entailment_checks e JOIN arguments a ON a.id=e.argument_id
                    WHERE e.id IN ({placeholders})
                    ORDER BY e.created_at,e.id""",
                requested_ids,
            ).fetchall()
        if len(rows) != len(requested_ids):
            found = {row["id"] for row in rows}
            missing = next(item for item in requested_ids if item not in found)
            raise KeyError(f"entailment not found: {missing}")

        entries = []
        evidence = []
        names: set[str] = set()
        languages: set[str] = set()
        methods: set[str] = set()
        issues: list[str] = []
        specifications: dict[str, ArgumentCreate] = {}
        for position, row in enumerate(rows):
            specification = ArgumentCreate.model_validate_json(row["specification_json"])
            specifications[row["id"]] = specification
            verdict, checked, premise_models, counterexample, entailment_hash = verify_argument(
                specification.premises,
                specification.conclusion,
                specification.variables,
            )
            argument_hash = canonical_hash(specification.model_dump(mode="json"))
            stored_counterexample = (
                json.loads(row["counterexample_json"])
                if row["counterexample_json"]
                else None
            )
            verification_valid = (
                argument_hash == row["argument_hash"]
                and entailment_hash == row["entailment_hash"]
                and verdict == row["verdict"]
                and checked == row["valuations_checked"]
                and premise_models == row["premise_models"]
                and counterexample == stored_counterexample
            )
            if not verification_valid:
                issues.append(f"proof_integrity_invalid:{row['id']}")
            names.add(specification.name)
            languages.add(specification.language)
            methods.add(row["method"])
            entry = {
                "position": position,
                "entailment_id": row["id"],
                "argument_id": row["argument_id"],
                "argument_name": specification.name,
                "verdict": verdict,
                "conclusion": specification.conclusion,
                "premises": specification.premises,
                "variables": specification.variables,
                "counterexample": counterexample,
                "premise_models": premise_models,
                "verification_valid": verification_valid,
                "argument_hash": argument_hash,
                "entailment_hash": entailment_hash,
                "created_at": row["created_at"],
            }
            entries.append(entry)
            evidence.append(
                {
                    "entailment_id": row["id"],
                    "stored_argument_hash": row["argument_hash"],
                    "computed_argument_hash": argument_hash,
                    "stored_entailment_hash": row["entailment_hash"],
                    "computed_entailment_hash": entailment_hash,
                    "stored_verdict": row["verdict"],
                    "computed_verdict": verdict,
                    "verification_valid": verification_valid,
                    "created_at": row["created_at"],
                }
            )

        if len(names) != 1:
            issues.append("incompatible_argument_names")
        if languages != {"propositional-v1"}:
            issues.append("incompatible_languages")
        if methods != {"truth-table-entailment-v1"}:
            issues.append("incompatible_entailment_methods")

        def formula_key(value: str) -> str:
            return "".join(value.split())

        dependencies = []
        for consumer_index, consumer in enumerate(entries):
            premise_keys = {
                formula_key(premise): premise for premise in consumer["premises"]
            }
            for provider in entries[:consumer_index]:
                key = formula_key(provider["conclusion"])
                if key in premise_keys:
                    dependencies.append(
                        {
                            "provider_entailment_id": provider["entailment_id"],
                            "consumer_entailment_id": consumer["entailment_id"],
                            "formula": premise_keys[key],
                        }
                    )
        dependencies.sort(
            key=lambda item: (
                item["consumer_entailment_id"],
                item["provider_entailment_id"],
                item["formula"],
            )
        )

        transitions = []
        for previous, current in zip(entries, entries[1:]):
            if (
                previous["verdict"] == "INCONSISTENT_PREMISES"
                or current["verdict"] == "INCONSISTENT_PREMISES"
            ):
                kind = "INSUFFICIENT_CHANGE"
                witness = current["counterexample"] or previous["counterexample"]
            elif previous["verdict"] == "ENTAILED" and current["verdict"] != "ENTAILED":
                kind = "REGRESSION"
                witness = current["counterexample"]
            elif previous["verdict"] != "ENTAILED" and current["verdict"] == "ENTAILED":
                kind = "RECOVERY"
                witness = previous["counterexample"]
            else:
                kind = "STABLE"
                witness = current["counterexample"]
            transitions.append(
                {
                    "from_entailment_id": previous["entailment_id"],
                    "to_entailment_id": current["entailment_id"],
                    "from_verdict": previous["verdict"],
                    "to_verdict": current["verdict"],
                    "kind": kind,
                    "witness": witness,
                }
            )

        streaks = []
        streak_start = 0
        for index in range(1, len(entries) + 1):
            if index == len(entries) or entries[index]["verdict"] != entries[streak_start]["verdict"]:
                streaks.append(
                    {
                        "verdict": entries[streak_start]["verdict"],
                        "length": index - streak_start,
                        "start_entailment_id": entries[streak_start]["entailment_id"],
                        "end_entailment_id": entries[index - 1]["entailment_id"],
                    }
                )
                streak_start = index
        longest_streak = max(streaks, key=lambda item: item["length"])
        severity = {"STABLE": 0, "RECOVERY": 1, "INSUFFICIENT_CHANGE": 2, "REGRESSION": 3}
        worst_transition = max(
            enumerate(transitions), key=lambda pair: (severity[pair[1]["kind"]], pair[0])
        )[1]
        regression_count = sum(item["kind"] == "REGRESSION" for item in transitions)
        recovery_count = sum(item["kind"] == "RECOVERY" for item in transitions)

        incompatibilities = [
            issue
            for issue in issues
            if issue.startswith("incompatible_") or issue.startswith("proof_integrity_invalid:")
        ]
        if incompatibilities:
            qualification = "INCOMPATIBLE"
        elif any(entry["verdict"] == "INCONSISTENT_PREMISES" for entry in entries):
            qualification = "INSUFFICIENT"
        else:
            significant = [
                item for item in transitions if item["kind"] in {"REGRESSION", "RECOVERY"}
            ]
            if not significant:
                qualification = "STABLE"
            elif significant[-1]["kind"] == "REGRESSION":
                qualification = "REGRESSED"
            else:
                qualification = "RECOVERED"

        chronological_ids = [entry["entailment_id"] for entry in entries]
        snapshot_hash = canonical_hash(
            {
                "chronological_entailment_ids": chronological_ids,
                "evidence": evidence,
                "dependencies": dependencies,
            }
        )
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT * FROM proof_stability_dossiers
                   WHERE input_hash=? AND snapshot_hash=? AND method=?""",
                (input_hash, snapshot_hash, data.method),
            ).fetchone()
        if existing:
            return self.proof_stability_dossier(existing, True)

        payload = {
            "entailment_ids": requested_ids,
            "chronological_entailment_ids": chronological_ids,
            "method": data.method,
            "qualification": qualification,
            "entries": entries,
            "transitions": transitions,
            "dependencies": dependencies,
            "regression_count": regression_count,
            "recovery_count": recovery_count,
            "longest_stable_streak": longest_streak,
            "worst_transition": worst_transition,
            "issues": sorted(issues),
            "snapshot_hash": snapshot_hash,
        }
        dossier_hash = canonical_hash(payload)
        dossier_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO proof_stability_dossiers
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    dossier_id,
                    input_hash,
                    json.dumps(requested_ids),
                    json.dumps(chronological_ids),
                    data.method,
                    qualification,
                    json.dumps(entries, sort_keys=True),
                    json.dumps(transitions, sort_keys=True),
                    json.dumps(dependencies, sort_keys=True),
                    regression_count,
                    recovery_count,
                    json.dumps(longest_streak, sort_keys=True),
                    json.dumps(worst_transition, sort_keys=True),
                    json.dumps(sorted(issues)),
                    snapshot_hash,
                    dossier_hash,
                    created,
                ),
            )
            self.audit(
                connection,
                "PROOF_STABILITY_ANALYZED",
                "proof_stability_dossier",
                dossier_id,
                {
                    "qualification": qualification,
                    "snapshot_hash": snapshot_hash,
                    "dossier_hash": dossier_hash,
                    "regression_count": regression_count,
                    "recovery_count": recovery_count,
                },
            )
            row = connection.execute(
                "SELECT * FROM proof_stability_dossiers WHERE id=?", (dossier_id,)
            ).fetchone()
        return self.proof_stability_dossier(row)

    def proof_stability_dossier(
        self, row, idempotent: bool = False
    ) -> ProofStabilityDossier:
        return ProofStabilityDossier(
            id=row["id"],
            entailment_ids=json.loads(row["entailment_ids_json"]),
            chronological_entailment_ids=json.loads(row["chronological_ids_json"]),
            method=row["method"],
            qualification=row["qualification"],
            entries=json.loads(row["entries_json"]),
            transitions=json.loads(row["transitions_json"]),
            dependencies=json.loads(row["dependencies_json"]),
            regression_count=row["regression_count"],
            recovery_count=row["recovery_count"],
            longest_stable_streak=json.loads(row["longest_streak_json"]),
            worst_transition=json.loads(row["worst_transition_json"]),
            issues=json.loads(row["issues_json"]),
            snapshot_hash=row["snapshot_hash"],
            dossier_hash=row["dossier_hash"],
            idempotent_replay=idempotent,
            created_at=row["created_at"],
        )

    def get_proof_stability_dossier(self, dossier_id: str) -> ProofStabilityDossier:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM proof_stability_dossiers WHERE id=?", (dossier_id,)
            ).fetchone()
        if not row:
            raise KeyError("proof stability dossier not found")
        return self.proof_stability_dossier(row)

    def list_proof_stability_dossiers(self) -> list[ProofStabilityDossier]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM proof_stability_dossiers
                   ORDER BY created_at DESC,rowid DESC"""
            ).fetchall()
        return [self.proof_stability_dossier(row) for row in rows]

    def create_proof_obligation_coverage_dossier(
        self, data: ProofObligationCoverageDossierCreate
    ) -> ProofObligationCoverageDossier:
        """Recompute exact premise coverage from persisted entailment evidence."""
        requested_ids = sorted(data.entailment_ids)
        input_hash = canonical_hash(
            {"entailment_ids": requested_ids, "method": data.method}
        )
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in requested_ids)
            rows = connection.execute(
                f"""SELECT e.*,a.argument_hash,a.specification_json
                    FROM entailment_checks e JOIN arguments a ON a.id=e.argument_id
                    WHERE e.id IN ({placeholders})
                    ORDER BY e.created_at,e.id""",
                requested_ids,
            ).fetchall()
        if len(rows) != len(requested_ids):
            found = {row["id"] for row in rows}
            missing = next(item for item in requested_ids if item not in found)
            raise KeyError(f"entailment not found: {missing}")

        def formula_key(value: str) -> str:
            return "".join(value.split())

        base_references = []
        evidence = []
        issues: list[str] = []
        languages: set[str] = set()
        methods: set[str] = set()
        providers: dict[str, list[str]] = {}
        for row in rows:
            specification = ArgumentCreate.model_validate_json(row["specification_json"])
            verdict, checked, premise_models, counterexample, entailment_hash = verify_argument(
                specification.premises,
                specification.conclusion,
                specification.variables,
            )
            argument_hash = canonical_hash(specification.model_dump(mode="json"))
            stored_counterexample = (
                json.loads(row["counterexample_json"])
                if row["counterexample_json"]
                else None
            )
            verification_valid = (
                argument_hash == row["argument_hash"]
                and entailment_hash == row["entailment_hash"]
                and verdict == row["verdict"]
                and checked == row["valuations_checked"]
                and premise_models == row["premise_models"]
                and counterexample == stored_counterexample
            )
            if not verification_valid:
                issues.append(f"proof_integrity_invalid:{row['id']}")
            if verdict != "ENTAILED":
                issues.append(f"provider_not_established:{row['id']}:{verdict}")
            languages.add(specification.language)
            methods.add(row["method"])
            if verification_valid and verdict == "ENTAILED":
                providers.setdefault(formula_key(specification.conclusion), []).append(
                    row["id"]
                )
            base_references.append(
                {
                    "entailment_id": row["id"],
                    "argument_id": row["argument_id"],
                    "argument_name": specification.name,
                    "conclusion": specification.conclusion,
                    "verdict": verdict,
                    "verification_valid": verification_valid,
                    "premises": specification.premises,
                    "argument_hash": argument_hash,
                    "entailment_hash": entailment_hash,
                    "created_at": row["created_at"],
                }
            )
            evidence.append(
                {
                    "entailment_id": row["id"],
                    "stored_argument_hash": row["argument_hash"],
                    "computed_argument_hash": argument_hash,
                    "stored_entailment_hash": row["entailment_hash"],
                    "computed_entailment_hash": entailment_hash,
                    "stored_verdict": row["verdict"],
                    "computed_verdict": verdict,
                    "verification_valid": verification_valid,
                    "created_at": row["created_at"],
                }
            )

        if languages != {"propositional-v1"}:
            issues.append("incompatible_languages")
        if methods != {"truth-table-entailment-v1"}:
            issues.append("incompatible_entailment_methods")
        for provider_ids in providers.values():
            provider_ids.sort()

        obligations = []
        used_provider_ids: set[str] = set()
        references = []
        for reference in base_references:
            covered_count = 0
            for premise_index, formula in enumerate(reference.pop("premises")):
                provider_ids = [
                    provider_id
                    for provider_id in providers.get(formula_key(formula), [])
                    if provider_id != reference["entailment_id"]
                ]
                status = "COVERED" if provider_ids else "UNCOVERED"
                covered_count += bool(provider_ids)
                used_provider_ids.update(provider_ids)
                obligations.append(
                    {
                        "consumer_entailment_id": reference["entailment_id"],
                        "premise_index": premise_index,
                        "formula": formula,
                        "status": status,
                        "provider_entailment_ids": provider_ids,
                    }
                )
            obligation_count = sum(
                obligation["consumer_entailment_id"] == reference["entailment_id"]
                for obligation in obligations
            )
            reference["obligation_count"] = obligation_count
            reference["covered_obligation_count"] = covered_count
            reference["coverage_ratio"] = round(covered_count / obligation_count, 6)
            references.append(reference)

        total_count = len(obligations)
        covered_count = sum(item["status"] == "COVERED" for item in obligations)
        uncovered_count = total_count - covered_count
        coverage_ratio = round(covered_count / total_count, 6)
        valid_provider_ids = {
            provider_id for provider_ids in providers.values() for provider_id in provider_ids
        }
        orphan_provider_ids = sorted(valid_provider_ids - used_provider_ids)
        worst_reference = min(
            references,
            key=lambda item: (item["coverage_ratio"], item["entailment_id"]),
        )
        integrity_issues = [
            issue
            for issue in issues
            if issue.startswith("proof_integrity_invalid:")
            or issue.startswith("incompatible_")
        ]
        if integrity_issues:
            qualification = "INCOMPATIBLE"
        elif any(item["verdict"] != "ENTAILED" for item in references):
            qualification = "INSUFFICIENT"
        elif uncovered_count:
            qualification = "GAPPED"
        else:
            qualification = "COMPLETE"

        ordered_ids = [row["id"] for row in rows]
        issues = sorted(issues)
        snapshot_hash = canonical_hash(
            {
                "ordered_entailment_ids": ordered_ids,
                "evidence": evidence,
                "obligations": obligations,
            }
        )
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT * FROM proof_obligation_coverage_dossiers
                   WHERE input_hash=? AND snapshot_hash=? AND method=?""",
                (input_hash, snapshot_hash, data.method),
            ).fetchone()
        if existing:
            return self.proof_obligation_coverage_dossier(existing, True)

        payload = {
            "entailment_ids": requested_ids,
            "ordered_entailment_ids": ordered_ids,
            "method": data.method,
            "qualification": qualification,
            "references": references,
            "obligations": obligations,
            "total_obligation_count": total_count,
            "covered_obligation_count": covered_count,
            "uncovered_obligation_count": uncovered_count,
            "coverage_ratio": coverage_ratio,
            "orphan_provider_entailment_ids": orphan_provider_ids,
            "worst_reference": worst_reference,
            "issues": issues,
            "snapshot_hash": snapshot_hash,
        }
        dossier_hash = canonical_hash(payload)
        dossier_id = str(uuid.uuid4())
        created = now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO proof_obligation_coverage_dossiers
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    dossier_id,
                    input_hash,
                    json.dumps(requested_ids),
                    json.dumps(ordered_ids),
                    data.method,
                    qualification,
                    json.dumps(references, sort_keys=True),
                    json.dumps(obligations, sort_keys=True),
                    total_count,
                    covered_count,
                    uncovered_count,
                    coverage_ratio,
                    json.dumps(orphan_provider_ids),
                    json.dumps(worst_reference, sort_keys=True),
                    json.dumps(issues),
                    snapshot_hash,
                    dossier_hash,
                    created,
                ),
            )
            self.audit(
                connection,
                "PROOF_OBLIGATION_COVERAGE_ANALYZED",
                "proof_obligation_coverage_dossier",
                dossier_id,
                {
                    "qualification": qualification,
                    "coverage_ratio": coverage_ratio,
                    "snapshot_hash": snapshot_hash,
                    "dossier_hash": dossier_hash,
                },
            )
            row = connection.execute(
                "SELECT * FROM proof_obligation_coverage_dossiers WHERE id=?",
                (dossier_id,),
            ).fetchone()
        return self.proof_obligation_coverage_dossier(row)

    def proof_obligation_coverage_dossier(
        self, row, idempotent: bool = False
    ) -> ProofObligationCoverageDossier:
        return ProofObligationCoverageDossier(
            id=row["id"],
            entailment_ids=json.loads(row["entailment_ids_json"]),
            ordered_entailment_ids=json.loads(row["ordered_ids_json"]),
            method=row["method"],
            qualification=row["qualification"],
            references=json.loads(row["references_json"]),
            obligations=json.loads(row["obligations_json"]),
            total_obligation_count=row["total_obligation_count"],
            covered_obligation_count=row["covered_obligation_count"],
            uncovered_obligation_count=row["uncovered_obligation_count"],
            coverage_ratio=row["coverage_ratio"],
            orphan_provider_entailment_ids=json.loads(row["orphan_provider_ids_json"]),
            worst_reference=json.loads(row["worst_reference_json"]),
            issues=json.loads(row["issues_json"]),
            snapshot_hash=row["snapshot_hash"],
            dossier_hash=row["dossier_hash"],
            idempotent_replay=idempotent,
            created_at=row["created_at"],
        )

    def get_proof_obligation_coverage_dossier(
        self, dossier_id: str
    ) -> ProofObligationCoverageDossier:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM proof_obligation_coverage_dossiers WHERE id=?",
                (dossier_id,),
            ).fetchone()
        if not row:
            raise KeyError("proof obligation coverage dossier not found")
        return self.proof_obligation_coverage_dossier(row)

    def list_proof_obligation_coverage_dossiers(
        self,
    ) -> list[ProofObligationCoverageDossier]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM proof_obligation_coverage_dossiers
                   ORDER BY created_at DESC,rowid DESC"""
            ).fetchall()
        return [self.proof_obligation_coverage_dossier(row) for row in rows]
