CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE propositions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposition_hash char(64) NOT NULL UNIQUE,
  specification jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE verifications(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposition_id uuid NOT NULL REFERENCES propositions(id),
  method text NOT NULL,
  verdict text NOT NULL CHECK(verdict IN ('VERIFIED','REFUTED')),
  valuations_checked integer NOT NULL,
  counterexample jsonb,
  verification_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(proposition_id,method)
);
CREATE TABLE arguments(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  argument_hash char(64) NOT NULL UNIQUE,
  specification jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE entailment_checks(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  argument_id uuid NOT NULL REFERENCES arguments(id),
  method text NOT NULL,
  verdict text NOT NULL CHECK(verdict IN ('ENTAILED','NOT_ENTAILED','INCONSISTENT_PREMISES')),
  valuations_checked integer NOT NULL,
  premise_models integer NOT NULL,
  counterexample jsonb,
  entailment_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(argument_id,method)
);
CREATE TABLE formula_comparisons(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  input_hash char(64) NOT NULL UNIQUE,
  specification jsonb NOT NULL,
  verdict text NOT NULL CHECK(verdict IN ('EQUIVALENT','NOT_EQUIVALENT')),
  valuations_checked integer NOT NULL,
  counterexample jsonb,
  comparison_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE premise_sets(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  premise_set_hash char(64) NOT NULL UNIQUE,
  specification jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE inconsistency_analyses(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  premise_set_id uuid NOT NULL REFERENCES premise_sets(id),
  method text NOT NULL CHECK(method='truth-table-minimal-unsat-core-v1'),
  verdict text NOT NULL CHECK(verdict IN ('CONSISTENT','INCONSISTENT')),
  valuations_checked integer NOT NULL,
  satisfying_assignment jsonb,
  core_indices jsonb NOT NULL,
  minimal_core jsonb NOT NULL,
  necessity_witnesses jsonb NOT NULL,
  minimality_verified boolean NOT NULL,
  analysis_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(premise_set_id,method)
);
CREATE TABLE proof_dependency_dossiers(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  root_entailment_id uuid NOT NULL REFERENCES entailment_checks(id),
  method text NOT NULL CHECK(method='exact-formula-dependency-v1'),
  input_hash char(64) NOT NULL UNIQUE,
  qualification text NOT NULL CHECK(qualification IN ('CLOSED','OPEN_ASSUMPTIONS','CYCLIC','INVALID')),
  nodes jsonb NOT NULL,
  edges jsonb NOT NULL,
  reachable_entailment_ids jsonb NOT NULL,
  unused_entailment_ids jsonb NOT NULL,
  open_assumptions jsonb NOT NULL,
  cycles jsonb NOT NULL,
  evidence_hash char(64) NOT NULL,
  dossier_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE multi_argument_coherence_dossiers(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  input_hash char(64) NOT NULL,
  entailment_ids jsonb NOT NULL,
  method text NOT NULL CHECK(method='truth-table-multi-conclusion-coherence-v1'),
  qualification text NOT NULL CHECK(qualification IN ('CONSISTENT','CONTRADICTORY','INSUFFICIENT','INCOMPATIBLE')),
  variables jsonb NOT NULL,
  canonical_conclusions jsonb NOT NULL,
  proofs jsonb NOT NULL,
  contradiction_witnesses jsonb NOT NULL,
  satisfying_assignment jsonb,
  issues jsonb NOT NULL,
  valuations_checked integer NOT NULL CHECK(valuations_checked>=0),
  snapshot_hash char(64) NOT NULL,
  dossier_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(input_hash,snapshot_hash,method)
);
CREATE INDEX multi_argument_coherence_input
ON multi_argument_coherence_dossiers(input_hash,created_at);
CREATE TABLE proof_stability_dossiers(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  input_hash char(64) NOT NULL,
  entailment_ids jsonb NOT NULL,
  chronological_entailment_ids jsonb NOT NULL,
  method text NOT NULL CHECK(method='chronological-entailment-stability-v1'),
  qualification text NOT NULL CHECK(qualification IN ('STABLE','REGRESSED','RECOVERED','INSUFFICIENT','INCOMPATIBLE')),
  entries jsonb NOT NULL,
  transitions jsonb NOT NULL,
  dependencies jsonb NOT NULL,
  regression_count integer NOT NULL CHECK(regression_count>=0),
  recovery_count integer NOT NULL CHECK(recovery_count>=0),
  longest_stable_streak jsonb NOT NULL,
  worst_transition jsonb NOT NULL,
  issues jsonb NOT NULL,
  snapshot_hash char(64) NOT NULL,
  dossier_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(input_hash,snapshot_hash,method)
);
CREATE INDEX proof_stability_input ON proof_stability_dossiers(input_hash,created_at);
CREATE TABLE proof_obligation_coverage_dossiers(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  input_hash char(64) NOT NULL,
  entailment_ids jsonb NOT NULL,
  ordered_entailment_ids jsonb NOT NULL,
  method text NOT NULL CHECK(method='exact-premise-obligation-coverage-v1'),
  qualification text NOT NULL CHECK(qualification IN ('COMPLETE','GAPPED','INSUFFICIENT','INCOMPATIBLE')),
  proof_references jsonb NOT NULL,
  obligations jsonb NOT NULL,
  total_obligation_count integer NOT NULL CHECK(total_obligation_count>=0),
  covered_obligation_count integer NOT NULL CHECK(covered_obligation_count>=0),
  uncovered_obligation_count integer NOT NULL CHECK(uncovered_obligation_count>=0),
  coverage_ratio double precision NOT NULL CHECK(coverage_ratio>=0 AND coverage_ratio<=1),
  orphan_provider_entailment_ids jsonb NOT NULL,
  worst_reference jsonb NOT NULL,
  issues jsonb NOT NULL,
  snapshot_hash char(64) NOT NULL,
  dossier_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(input_hash,snapshot_hash,method)
);
CREATE INDEX proof_obligation_coverage_input
ON proof_obligation_coverage_dossiers(input_hash,created_at);
CREATE TABLE audit_events(
  id bigserial PRIMARY KEY,event_type text NOT NULL,entity_type text NOT NULL,
  entity_id text NOT NULL,payload jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION reject_proofforge_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'ProofForge records are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER propositions_immutable BEFORE UPDATE OR DELETE ON propositions
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER verifications_immutable BEFORE UPDATE OR DELETE ON verifications
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER arguments_immutable BEFORE UPDATE OR DELETE ON arguments
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER entailment_checks_immutable BEFORE UPDATE OR DELETE ON entailment_checks
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER formula_comparisons_immutable BEFORE UPDATE OR DELETE ON formula_comparisons
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER premise_sets_immutable BEFORE UPDATE OR DELETE ON premise_sets
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER inconsistency_analyses_immutable BEFORE UPDATE OR DELETE ON inconsistency_analyses
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER proof_dependency_dossiers_immutable BEFORE UPDATE OR DELETE ON proof_dependency_dossiers
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER multi_argument_coherence_dossiers_immutable BEFORE UPDATE OR DELETE ON multi_argument_coherence_dossiers
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER proof_stability_dossiers_immutable BEFORE UPDATE OR DELETE ON proof_stability_dossiers
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER proof_obligation_coverage_dossiers_immutable BEFORE UPDATE OR DELETE ON proof_obligation_coverage_dossiers
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION reject_proofforge_mutation();
