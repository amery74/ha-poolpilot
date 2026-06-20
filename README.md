# Pool Pilot v0.2.4

Correctifs pour le dashboard v0.14 :

- Service `pool_pilot.add_product` plus tolérant avec les champs envoyés par le Pool House.
- `category` reste optionnel et accepte aussi `product_type`.
- Conservation des métadonnées produit : marque, forme, poids unitaire, dissolution, stabilisant, lieu de traitement, dosage choc et dosage initial.
- Capteur `sensor.*_pool_house` exposant `attributes.products`.
- Boutons disponibles : `Valider action recommandée`, `Filtration auto recommandée`, `Démarrer pompe`, `Arrêter pompe`.
