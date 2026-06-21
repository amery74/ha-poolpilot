# Pool Pilot v0.4.0

Version simplifiée et alignée avec le dashboard.

## Configuration obligatoire
- Volume du bassin en m³
- Température eau
- pH
- Chlore libre ou ORP
- Pompe de filtration, un seul switch ON/OFF
- Entité météo `weather.xxx`

## Supprimé de l'assistant d'installation
- PAC
- Volet / cover
- Température prévue séparée
- TAC / TH / Stabilisant comme entités

Ces éléments sont soit configurés dans le dashboard, soit renseignés manuellement via le Mode Expert.

## Nouveau
- Service `pool_pilot.update_strip_test`
- Capteur `strip_test`
- Capteur `raw_measurements`
- Calcul filtration basé sur température eau + météo + volume
- Flux de configuration réécrit pour corriger l'erreur 500 lors de la reconfiguration.
