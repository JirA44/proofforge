# Proofforge — Présentation complète

## Présentation
proofforge est un registre immuable, hashé (SHA-256), auditable et rejouable.

## À quoi ça sert ? (problèmes réglés)
- **Preuve orale non rejouable** → résolu par un dossier déterministe, ordre-indépendant
- **Argument qui semble valide mais a une prémisse incohérente** → résolu par un dossier déterministe, ordre-indépendant
- **Obligation de preuve oubliée dans un dossier** → résolu par un dossier déterministe, ordre-indépendant

## Cas d'utilisation concrets
- Thèse / mémoire: vérifier que chaque prémisse est couverte par une preuve antérieure
- Dossier réglementaire (médical/finance): produire un dossier de couverture opposable
- Revue par les pairs: détecter le chaînage manquant entre lemmes

## Exemples d'utilisation (API)
```bash
curl -X POST http://localhost:8000/v1/proof-obligation-coverage-dossiers -H 'Content-Type: application/json' -d '{"entailment_ids": ["uuid1", "uuid2"]}'
# → { "qualification": "COMPLETE|GAPPED|INSUFFICIENT|INCOMPATIBLE", "coverage_ratio": 0.94, ... }
```

## À quoi ça pourrait servir (futur / possibilités)
- IA explicable: attester qu'une décision IA repose sur des prémisses prouvées
- Smart contracts: ancrer des preuves logiques on-chain
- Certification: générer un hash SHA-256 opposable d un dossier complet

## Pour qui ?
Devs, auditeurs, ops, chercheurs — qui ont besoin d'une preuve opposable, pas d'un verdict déclaratif.