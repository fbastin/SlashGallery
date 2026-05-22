# SlashGallery Library

Une librairie PHP/Python modulaire pour créer des galeries photos intelligentes avec recherche, IA, chronologie et cartes.

## Installation

1. Copiez le dossier `slash-gallery` dans votre projet.
2. Configurez votre environnement virtuel Python avec `torch`, `torchvision`, `pillow` et `translate`.
3. Initialisez la classe PHP :

```php
require_once 'slash-gallery/src/SlashGallery.php';

$gallery = new SlashGallery([
    'db_path' => '/chemin/vers/votre/base.db',
    'photo_base_dir' => '/chemin/vers/vos/photos',
    'python_venv' => '/chemin/vers/votre/venv'
]);
```

## Structure
- `src/` : Code source PHP (Core).
- `backend/` : Scripts Python (IA, Indexation, SQLite).
- `css/` / `js/` : Assets pour l'interface.
- `models/` : Stockage des modèles d'IA personnalisés.

## Fonctionnalités
- **Recherche Instantanée** via SQLite.
- **Auto-tagging IA** avec ResNet-50.
- **Apprentissage continu** (Fine-tuning) basé sur vos corrections.
- **Vue Chronologique** et **Carte interactive** (Leaflet/OSM).
- **Export ZIP** de sélections personnalisées.
```
