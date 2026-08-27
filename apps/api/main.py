import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

from . import __version__
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
from .repository import Repository


app=FastAPI(title="ProofForge API",version=__version__,description="Propositions, arguments, cohérence, stabilité et couverture d'obligations de preuves immuables avec vérification machine déterministe.")
DB_PATH=os.getenv("PROOFFORGE_DB",str(Path(__file__).resolve().parents[2]/"proofforge.db"))
repo=Repository(DB_PATH)


@app.get("/health")
def health(): return {"status":"ok","version":__version__}


@app.get("/info")
def info():
    return {
        "name":"ProofForge",
        "version":__version__,
        "release":"V1.07",
        "capabilities":["tautology","entailment","equivalence","minimal-inconsistent-core","proof-dependency-closure","multi-argument-coherence","chronological-proof-stability","proof-obligation-coverage"],
    }


@app.post("/v1/propositions",response_model=Proposition,status_code=201)
def create_proposition(data: PropositionCreate): return repo.create_proposition(data)


@app.get("/v1/propositions",response_model=list[Proposition])
def list_propositions(): return repo.list_propositions()


@app.post("/v1/verifications",response_model=Verification,status_code=201)
def create_verification(data: VerificationCreate):
    try: return repo.verify(data)
    except KeyError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@app.post("/v1/arguments", response_model=Argument, status_code=201)
def create_argument(data: ArgumentCreate):
    return repo.create_argument(data)


@app.get("/v1/arguments", response_model=list[Argument])
def list_arguments():
    return repo.list_arguments()


@app.post("/v1/entailments", response_model=EntailmentCheck, status_code=201)
def check_entailment(data: EntailmentCheckCreate):
    try:
        return repo.check_entailment(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/formula-comparisons", response_model=FormulaComparison, status_code=201)
def compare_formulae(data: FormulaComparisonCreate):
    try:
        return repo.compare(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/formula-comparisons", response_model=list[FormulaComparison])
def list_formula_comparisons():
    return repo.list_formula_comparisons()


@app.get(
    "/v1/formula-comparisons/{comparison_id}", response_model=FormulaComparison
)
def get_formula_comparison(comparison_id: str):
    try:
        return repo.get_formula_comparison(comparison_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/premise-sets", response_model=PremiseSet, status_code=201)
def create_premise_set(data: PremiseSetCreate):
    return repo.create_premise_set(data)


@app.get("/v1/premise-sets", response_model=list[PremiseSet])
def list_premise_sets():
    return repo.list_premise_sets()


@app.post(
    "/v1/inconsistency-analyses",
    response_model=InconsistencyAnalysis,
    status_code=201,
)
def analyze_inconsistency(data: InconsistencyAnalysisCreate):
    try:
        return repo.analyze_premise_set(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/v1/inconsistency-analyses/{analysis_id}",
    response_model=InconsistencyAnalysis,
)
def get_inconsistency_analysis(analysis_id: str):
    try:
        return repo.get_inconsistency_analysis(analysis_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/v1/proof-dependency-dossiers",
    response_model=ProofDependencyDossier,
    status_code=201,
)
def create_proof_dependency_dossier(data: ProofDependencyDossierCreate):
    try:
        return repo.create_proof_dependency_dossier(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/v1/proof-dependency-dossiers",
    response_model=list[ProofDependencyDossier],
)
def list_proof_dependency_dossiers():
    return repo.list_proof_dependency_dossiers()


@app.get(
    "/v1/proof-dependency-dossiers/{dossier_id}",
    response_model=ProofDependencyDossier,
)
def get_proof_dependency_dossier(dossier_id: str):
    try:
        return repo.get_proof_dependency_dossier(dossier_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/v1/multi-argument-coherence-dossiers",
    response_model=MultiArgumentCoherenceDossier,
    status_code=201,
)
def create_multi_argument_coherence_dossier(data: MultiArgumentCoherenceCreate):
    try:
        return repo.create_multi_argument_coherence_dossier(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/v1/multi-argument-coherence-dossiers",
    response_model=list[MultiArgumentCoherenceDossier],
)
def list_multi_argument_coherence_dossiers():
    return repo.list_multi_argument_coherence_dossiers()


@app.get(
    "/v1/multi-argument-coherence-dossiers/{dossier_id}",
    response_model=MultiArgumentCoherenceDossier,
)
def get_multi_argument_coherence_dossier(dossier_id: str):
    try:
        return repo.get_multi_argument_coherence_dossier(dossier_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/v1/proof-stability-dossiers",
    response_model=ProofStabilityDossier,
    status_code=201,
)
def create_proof_stability_dossier(data: ProofStabilityDossierCreate):
    try:
        return repo.create_proof_stability_dossier(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/proof-stability-dossiers", response_model=list[ProofStabilityDossier])
def list_proof_stability_dossiers():
    return repo.list_proof_stability_dossiers()


@app.get(
    "/v1/proof-stability-dossiers/{dossier_id}",
    response_model=ProofStabilityDossier,
)
def get_proof_stability_dossier(dossier_id: str):
    try:
        return repo.get_proof_stability_dossier(dossier_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/v1/proof-obligation-coverage-dossiers",
    response_model=ProofObligationCoverageDossier,
    status_code=201,
)
def create_proof_obligation_coverage_dossier(
    data: ProofObligationCoverageDossierCreate,
):
    try:
        return repo.create_proof_obligation_coverage_dossier(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/v1/proof-obligation-coverage-dossiers",
    response_model=list[ProofObligationCoverageDossier],
)
def list_proof_obligation_coverage_dossiers():
    return repo.list_proof_obligation_coverage_dossiers()


@app.get(
    "/v1/proof-obligation-coverage-dossiers/{dossier_id}",
    response_model=ProofObligationCoverageDossier,
)
def get_proof_obligation_coverage_dossier(dossier_id: str):
    try:
        return repo.get_proof_obligation_coverage_dossier(dossier_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
