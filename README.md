# Pool Pilot v0.4.2

Corrections :
- l'intégration garde une seule entité utile pour l'auto quotidienne : le switch/bouton de filtration automatique Pool Pilot ;
- les capteurs techniques `statut filtration auto`, `temps restant auto`, `statut planification` et `prochain démarrage` ne sont plus créés pour les nouvelles installations ;
- le calcul de filtration météo reste côté Pool Pilot via l'entité `weather.xxx` configurée dans l'intégration.

Note : Home Assistant peut conserver d'anciennes entités déjà créées dans le registre. Elles peuvent être supprimées manuellement depuis Paramètres > Appareils et services > Entités si elles ne servent plus.
