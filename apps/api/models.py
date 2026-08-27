from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def validate_variables(variables: list[str]) -> list[str]:
    if len(variables) != len(set(variables)):
        raise ValueError("variables must be unique")
    if any(
        not variable.replace("_", "").isalnum() or variable[0].isdigit()
        for variable in variables
    ):
        raise ValueError("invalid variable name")
    return variables


class PropositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    formal_expression: str = Field(min_length=1,max_length=1000)
    variables: list[str] = Field(min_length=1,max_length=8)
    language: str = Field(default="propositional-v1",pattern="^propositional-v1$")

    @model_validator(mode="after")
    def validate_variables(self):
        validate_variables(self.variables)
        return self


class Proposition(BaseModel):
    id: str
    proposition_hash: str
    specification: PropositionCreate
    immutable: bool = True
    created_at: str


class VerificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposition_id: str
    method: str = Field(default="truth-table-v1",pattern="^truth-table-v1$")


class Verification(BaseModel):
    id: str
    proposition_id: str
    method: str
    verdict: str
    valuations_checked: int
    counterexample: dict[str,bool] | None = None
    verification_hash: str
    reproducible: bool
    idempotent_replay: bool = False
    created_at: str
    warning: str = "Verdict limité au langage formel vérifié ; aucune vérité empirique n’est déduite."


class ArgumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    premises: list[str] = Field(min_length=1, max_length=32)
    conclusion: str = Field(min_length=1, max_length=1000)
    variables: list[str] = Field(min_length=1, max_length=8)
    language: str = Field(default="propositional-v1", pattern="^propositional-v1$")

    @model_validator(mode="after")
    def validate_argument(self):
        validate_variables(self.variables)
        if len(self.premises) != len(set(self.premises)):
            raise ValueError("premises must be unique")
        return self


class Argument(BaseModel):
    id: str
    argument_hash: str
    specification: ArgumentCreate
    immutable: bool = True
    created_at: str


class EntailmentCheckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    argument_id: str = Field(min_length=1)
    method: Literal["truth-table-entailment-v1"] = "truth-table-entailment-v1"


class EntailmentCheck(BaseModel):
    id: str
    argument_id: str
    method: str
    verdict: Literal["ENTAILED", "NOT_ENTAILED", "INCONSISTENT_PREMISES"]
    valuations_checked: int
    premise_models: int
    counterexample: dict[str, bool] | None = None
    entailment_hash: str
    reproducible: bool = True
    idempotent_replay: bool = False
    immutable: bool = True
    created_at: str
    warning: str = (
        "Entaillement limité au langage formel déclaré ; il ne valide ni les prémisses "
        "dans le monde réel ni une vérité empirique."
    )


class FormulaComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    left_expression: str = Field(min_length=1, max_length=1000)
    right_expression: str = Field(min_length=1, max_length=1000)
    variables: list[str] = Field(min_length=1, max_length=8)
    method: Literal["truth-table-equivalence-v1"] = "truth-table-equivalence-v1"

    @model_validator(mode="after")
    def validate_comparison(self):
        validate_variables(self.variables)
        return self


class FormulaCounterexample(BaseModel):
    valuation: dict[str, bool]
    left_value: bool
    right_value: bool


class FormulaComparison(BaseModel):
    id: str
    input_hash: str
    specification: FormulaComparisonCreate
    verdict: Literal["EQUIVALENT", "NOT_EQUIVALENT"]
    valuations_checked: int
    counterexample: FormulaCounterexample | None = None
    comparison_hash: str
    reproducible: bool = True
    idempotent_replay: bool = False
    immutable: bool = True
    created_at: str
    warning: str = (
        "Équivalence limitée au langage formel déclaré ; elle ne démontre aucune "
        "équivalence empirique entre les phénomènes éventuellement représentés."
    )


class PremiseSetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    premises: list[str] = Field(min_length=1, max_length=32)
    variables: list[str] = Field(min_length=1, max_length=8)
    language: Literal["propositional-v1"] = "propositional-v1"

    @model_validator(mode="after")
    def validate_premise_set(self):
        validate_variables(self.variables)
        if len(self.premises) != len(set(self.premises)):
            raise ValueError("premises must be unique")
        if any(not premise.strip() for premise in self.premises):
            raise ValueError("premises must not be blank")
        return self


class PremiseSet(BaseModel):
    id: str
    premise_set_hash: str
    specification: PremiseSetCreate
    immutable: bool = True
    created_at: str


class InconsistencyAnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premise_set_id: str = Field(min_length=1)
    method: Literal["truth-table-minimal-unsat-core-v1"] = (
        "truth-table-minimal-unsat-core-v1"
    )


class NecessityWitness(BaseModel):
    removed_index: int = Field(ge=0)
    removed_premise: str
    valuation: dict[str, bool] | None


class InconsistencyAnalysis(BaseModel):
    id: str
    premise_set_id: str
    method: str
    verdict: Literal["CONSISTENT", "INCONSISTENT"]
    valuations_checked: int
    satisfying_assignment: dict[str, bool] | None = None
    core_indices: list[int]
    minimal_core: list[str]
    necessity_witnesses: list[NecessityWitness]
    minimality_verified: bool
    analysis_hash: str
    reproducible: bool = True
    immutable: bool = True
    idempotent_replay: bool = False
    created_at: str
    warning: str = (
        "Cohérence limitée au calcul propositionnel déclaré : le noyau est minimal "
        "par inclusion, pas nécessairement de cardinalité minimale, et ne juge aucune "
        "vérité empirique."
    )


class ProofDependencyDossierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_entailment_id: str = Field(min_length=1)
    supporting_entailment_ids: list[str] = Field(default_factory=list, max_length=49)
    method: Literal["exact-formula-dependency-v1"] = "exact-formula-dependency-v1"

    @model_validator(mode="after")
    def validate_ids(self):
        if len(self.supporting_entailment_ids) != len(set(self.supporting_entailment_ids)):
            raise ValueError("supporting_entailment_ids must be unique")
        if self.root_entailment_id in self.supporting_entailment_ids:
            raise ValueError("root_entailment_id must not be repeated as support")
        return self


class ProofDependencyNode(BaseModel):
    entailment_id: str
    argument_id: str
    conclusion: str
    premises: list[str]
    verdict: str
    verification_valid: bool


class ProofDependencyEdge(BaseModel):
    provider_entailment_id: str
    consumer_entailment_id: str
    formula: str


class ProofDependencyDossier(BaseModel):
    id: str
    root_entailment_id: str
    method: str
    qualification: Literal["CLOSED", "OPEN_ASSUMPTIONS", "CYCLIC", "INVALID"]
    nodes: list[ProofDependencyNode]
    edges: list[ProofDependencyEdge]
    reachable_entailment_ids: list[str]
    unused_entailment_ids: list[str]
    open_assumptions: list[str]
    cycles: list[list[str]]
    evidence_hash: str
    dossier_hash: str
    immutable: bool = True
    reproducible: bool = True
    idempotent_replay: bool = False
    created_at: str
    warning: str = (
        "La fermeture porte uniquement sur les formules exactes et les preuves fournies. "
        "Elle ne démontre ni la vérité empirique des hypothèses ni leur pertinence."
    )


class MultiArgumentCoherenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entailment_ids: list[str] = Field(min_length=2, max_length=50)
    method: Literal["truth-table-multi-conclusion-coherence-v1"] = (
        "truth-table-multi-conclusion-coherence-v1"
    )

    @model_validator(mode="after")
    def validate_entailment_ids(self):
        if len(self.entailment_ids) != len(set(self.entailment_ids)):
            raise ValueError("entailment_ids must be unique")
        if any(not value or len(value) > 100 for value in self.entailment_ids):
            raise ValueError("entailment_ids must contain 1 to 100 characters")
        return self


class CoherenceProof(BaseModel):
    entailment_id: str
    argument_id: str
    conclusion: str
    variables: list[str]
    verdict: str
    verification_valid: bool
    argument_hash: str
    entailment_hash: str


class CoherenceNecessityWitness(BaseModel):
    entailment_ids: list[str]
    conclusion: str
    valuation: dict[str, bool] | None


class ContradictionWitness(BaseModel):
    kind: Literal["LOGICAL_NEGATION_OR_INCOMPATIBILITY", "JOINT_IMPOSSIBILITY"]
    entailment_ids: list[str]
    conclusions: list[str]
    necessity_witnesses: list[CoherenceNecessityWitness]


class MultiArgumentCoherenceDossier(BaseModel):
    id: str
    entailment_ids: list[str]
    method: str
    qualification: Literal[
        "CONSISTENT", "CONTRADICTORY", "INSUFFICIENT", "INCOMPATIBLE"
    ]
    variables: list[str]
    canonical_conclusions: list[str]
    proofs: list[CoherenceProof]
    contradiction_witnesses: list[ContradictionWitness]
    satisfying_assignment: dict[str, bool] | None = None
    issues: list[str]
    valuations_checked: int = Field(ge=0)
    snapshot_hash: str
    dossier_hash: str
    immutable: bool = True
    reproducible: bool = True
    idempotent_replay: bool = False
    created_at: str
    warning: str = (
        "La cohérence est limitée au calcul propositionnel déclaré et aux preuves "
        "persistées ; elle ne démontre ni vérité empirique ni compatibilité métier."
    )


class ProofStabilityDossierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entailment_ids: list[str] = Field(min_length=2, max_length=100)
    method: Literal["chronological-entailment-stability-v1"] = (
        "chronological-entailment-stability-v1"
    )

    @model_validator(mode="after")
    def validate_ids(self):
        if len(self.entailment_ids) != len(set(self.entailment_ids)):
            raise ValueError("entailment_ids must be unique")
        if any(not value or len(value) > 100 for value in self.entailment_ids):
            raise ValueError("entailment_ids must contain 1 to 100 characters")
        return self


class StabilityEntry(BaseModel):
    position: int = Field(ge=0)
    entailment_id: str
    argument_id: str
    argument_name: str
    verdict: str
    conclusion: str
    premises: list[str]
    variables: list[str]
    counterexample: dict[str, bool] | None
    premise_models: int = Field(ge=0)
    verification_valid: bool
    argument_hash: str
    entailment_hash: str
    created_at: str


class StabilityTransition(BaseModel):
    from_entailment_id: str
    to_entailment_id: str
    from_verdict: str
    to_verdict: str
    kind: Literal["STABLE", "REGRESSION", "RECOVERY", "INSUFFICIENT_CHANGE"]
    witness: dict[str, bool] | None


class StabilityDependency(BaseModel):
    provider_entailment_id: str
    consumer_entailment_id: str
    formula: str


class StableStreak(BaseModel):
    verdict: str
    length: int = Field(ge=1)
    start_entailment_id: str
    end_entailment_id: str


class ProofStabilityDossier(BaseModel):
    id: str
    entailment_ids: list[str]
    chronological_entailment_ids: list[str]
    method: str
    qualification: Literal[
        "STABLE", "REGRESSED", "RECOVERED", "INSUFFICIENT", "INCOMPATIBLE"
    ]
    entries: list[StabilityEntry]
    transitions: list[StabilityTransition]
    dependencies: list[StabilityDependency]
    regression_count: int = Field(ge=0)
    recovery_count: int = Field(ge=0)
    longest_stable_streak: StableStreak
    worst_transition: StabilityTransition
    issues: list[str]
    snapshot_hash: str
    dossier_hash: str
    immutable: bool = True
    reproducible: bool = True
    idempotent_replay: bool = False
    created_at: str
    warning: str = (
        "La stabilité décrit uniquement des transitions formelles recalculées. Elle "
        "ne prouve aucune vérité empirique et n’accorde aucune autorisation automatique."
    )


class ProofObligationCoverageDossierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entailment_ids: list[str] = Field(min_length=2, max_length=100)
    method: Literal["exact-premise-obligation-coverage-v1"] = (
        "exact-premise-obligation-coverage-v1"
    )

    @model_validator(mode="after")
    def validate_ids(self):
        if len(self.entailment_ids) != len(set(self.entailment_ids)):
            raise ValueError("entailment_ids must be unique")
        if any(not value or len(value) > 100 for value in self.entailment_ids):
            raise ValueError("entailment_ids must contain 1 to 100 characters")
        return self


class ProofObligation(BaseModel):
    consumer_entailment_id: str
    premise_index: int = Field(ge=0)
    formula: str
    status: Literal["COVERED", "UNCOVERED"]
    provider_entailment_ids: list[str]


class ProofCoverageReference(BaseModel):
    entailment_id: str
    argument_id: str
    argument_name: str
    conclusion: str
    verdict: str
    verification_valid: bool
    obligation_count: int = Field(ge=0)
    covered_obligation_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    argument_hash: str
    entailment_hash: str
    created_at: str


class ProofObligationCoverageDossier(BaseModel):
    id: str
    entailment_ids: list[str]
    ordered_entailment_ids: list[str]
    method: str
    qualification: Literal["COMPLETE", "GAPPED", "INSUFFICIENT", "INCOMPATIBLE"]
    references: list[ProofCoverageReference]
    obligations: list[ProofObligation]
    total_obligation_count: int = Field(ge=0)
    covered_obligation_count: int = Field(ge=0)
    uncovered_obligation_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    orphan_provider_entailment_ids: list[str]
    worst_reference: ProofCoverageReference
    issues: list[str]
    snapshot_hash: str
    dossier_hash: str
    immutable: bool = True
    reproducible: bool = True
    idempotent_replay: bool = False
    created_at: str
    warning: str = (
        "La couverture repose uniquement sur la correspondance exacte entre conclusions "
        "formellement vérifiées et prémisses sélectionnées. Elle ne prouve ni la vérité "
        "empirique des prémisses ni l'exhaustivité des obligations métier."
    )
