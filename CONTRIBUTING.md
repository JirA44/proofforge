# Contribuer à ProofForge

1. Créez une branche courte depuis la branche principale.
2. Installez le projet avec `python -m pip install -e ".[dev]"`.
3. Ajoutez des tests cumulatifs : aucun test historique ne doit être supprimé.
4. Exécutez `python -m pytest -q` et `python -m compileall -q apps packages`.
5. Toute modification fonctionnelle incrémente la version et documente le contrat OpenAPI.

Les verdicts, preuves et qualifications doivent être recalculés côté serveur. Une contribution ne doit jamais introduire un résultat client présenté comme vérifié.
