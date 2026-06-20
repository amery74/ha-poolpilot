# Pool Pilot v0.2.2

Corrections pour le dashboard v0.12 :
- service `pool_pilot.add_product` tolère les champs supplémentaires envoyés par le Pool House ;
- catégories `anti_algae` / `wintering` supportées ;
- le capteur `Pool House` expose les produits dans ses attributs `products` avec marque, forme, dosage et stock ;
- entités utiles pour la carte : `sensor.*_alert_status`, `sensor.*_pool_house`, `button.*_confirm_current_action`, `button.*_start_auto_filter`.
