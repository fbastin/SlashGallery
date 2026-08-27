# Guide d'utilisation — SlashGallery

Ce guide documente comment intégrer la bibliothèque `SlashGallery` dans votre propre
application PHP et comment utiliser le backend Python.

---

## 1. Prérequis

- **PHP 7.4+** avec `shell_exec` activé (utilisé pour piloter le backend Python).
- **Python 3.8+** avec les paquets :
  - `torch`, `torchvision` (auto-tagging ResNet-50)
  - `pillow` (miniatures, EXIF)
  - `translate` (traduction française des étiquettes IA)
  - `sqlite3` (inclus dans la stdlib)

> Les fonctionnalités non-IA (recherche, albums, cartes, chronologie, miniatures)
> ne nécessitent PAS torch. Seuls `aiTagImage`, `aiTagAlbum` et `fineTune` en ont besoin.

---

## 2. Installation

Copiez le dossier projet dans votre application puis chargez la classe :

```php
require_once 'slash-gallery/src/SlashGallery.php';
```

Créez un environnement virtuel Python (optionnel mais recommandé) :

```bash
python3 -m venv /chemin/vers/venv
/chemin/vers/venv/bin/pip install torch torchvision pillow translate
```

---

## 3. Configuration

### 3.1 Options du constructeur

```php
$gallery = new SlashGallery([
    'db_path'        => '/chemin/vers/base.db',   // base SQLite (créée si absente)
    'photo_base_dir' => '/chemin/vers/vos/photos',// racine des images
    'python_venv'    => '/chemin/vers/venv',      // env. Python (répertoire, PAS le binaire)

    // Options avec valeurs par défaut :
    'backend_dir'  => __DIR__ . '/slash-gallery/backend',
    'base_url'     => '/photos/',
    'labels_path'  => __DIR__ . '/slash-gallery/imagenet_classes.txt',
    'models_dir'   => __DIR__ . '/slash-gallery/models',
]);
```

| Option | Défaut | Rôle |
|---|---|---|
| `db_path` | `''` | Chemin du fichier SQLite. **Requis.** |
| `photo_base_dir` | `''` | Racine des photos. **Requis.** Les chemins manipulés sont relatifs à cette racine. |
| `python_venv` | `''` | Répertoire du venv Python. Si vide, `python` du PATH est utilisé. |
| `backend_dir` | `__DIR__/../backend` | Scripts Python. |
| `base_url` | `/photos/` | URL publique de la galerie (non utilisée par le backend). |
| `labels_path` | `__DIR__/../imagenet_classes.txt` | Classes ImageNet. |
| `models_dir` | `__DIR__/../models` | Modèles d'IA personnalisés (fine-tuning). |

### 3.2 Contexte de sécurité

La bibliothèque respecte la visibilité des photos. Définissez le contexte de
**chaque requête** selon l'utilisateur courant :

```php
// Administrateur : voit tout.
$gallery->setSecurityContext(true);

// Membre : ne voit que les photos publiques + celles portant son étiquette personnelle.
$gallery->setSecurityContext(false, 'mon_pseudo');
```

Les opérations sensibles (`deleteImage`, `setPublic`, `setLicense`, `setMessageId`,
`deleteByMessageId`, `deleteAlbum`) ne sont autorisées que pour le contexte admin.

---

## 4. Recherche et navigation

```php
// Recherche par mots-clés (nom de fichier + étiquettes).
$results = $gallery->search('montagne', null);
foreach ($results as $r) {
    echo $r['path'] . ' (' . $r['lat'] . ', ' . $r['lng'] . ')' . "\n";
}

// Filtrage par étiquette en parallèle de la recherche.
$results = $gallery->search('plage', 'vacances');

// Toutes les images (optionnellement filtrées par étiquette).
$images = $gallery->getAllImages('amérique');

// Photos géolocalisées (pour la carte).
$geolocated = $gallery->getGeolocated();

// Photographie aléatoire (filtrée par visibilité).
$random = $gallery->getRandomImages(24);
```

### Chronologie

```php
$timeline = $gallery->getTimeline();
// [['day' => '2024-06-05', 'count' => 12], ...]
```

---

## 5. Albums

### 5.1 Albums « dossier » (basés sur le système de fichiers)

La bibliothèque travaille avec des chemins relatifs à `photo_base_dir`. Un
répertoire est un album de fait.

```php
// Choisit une image au hasard dans un dossier pour en faire la vignette de couverture.
$cover = $gallery->getAlbumFolderCover('vacances/été/plage');
// ['path' => 'vacances/été/plage/DSC00123.jpg'] ou null si dossier vide/invalide
```

> Sert à afficher chaque dossier-album avec une image illustrant son contenu.

### 5.2 Albums « collection » (base de données)

Des albums indépendants de l'arborescence, gérés par la base SQLite :

```php
// Créer un album.
$res = $gallery->createAlbum('Mon album préféré', 'Quelques coups de cœur');
$albumId = $res['album_id'];

// Lister les albums (avec le nombre de photos visibles).
$albums = $gallery->listAlbums();

// Afficher le contenu d'un album (selon la visibilité de l'utilisateur).
$album = $gallery->getAlbum($albumId);
// ['success' => true, 'name' => ..., 'description' => ..., 'images' => [{'path' => ...}, ...]]

// Ajouter / retirer des photos.
$gallery->addImageToAlbum($albumId, 'photos/DSC0001.jpg');
$gallery->removeImageFromAlbum($albumId, 'photos/DSC0001.jpg');

// Supprimer l'album (admin requis côté API).
$gallery->deleteAlbum($albumId);
```

> `addImageToAlbum` enregistre automatiquement la photo dans la table `images` si
> elle n'y figure pas encore (elle doit exister sur le disque).

---

## 6. Étiquettes

```php
// Ajouter / retirer une étiquette manuelle.
$gallery->addTag('photos/chat.jpg', 'animal');
$gallery->deleteTag('photos/chat.jpg', 'animal');

// Toutes les étiquettes avec leur fréquence.
$tags = $gallery->getAllTags(); // [['tag_name' => ..., 'count' => ...]]

// Métadonnées groupées pour une page de galerie.
$meta = $gallery->getBatchMetadata(['photos/a.jpg', 'photos/b.jpg']);
// ['tags' => [path => [{tag_name, source}], ...], 'meta' => [path => {lat, lng, date, is_public, license}]]
```

---

## 7. IA (auto-tagging ResNet-50)

```php
// Tagger une image.
$res = $gallery->aiTagImage('photos/chat.jpg');
// ['success' => true, 'tags' => ['cat', 'chat', ...]]

// Tagger toutes les images d'un dossier.
$res = $gallery->aiTagAlbum('vacances');
// ['success' => true, 'processed' => 42, 'errors' => [...]]

// Apprentissage continu (fine-tuning) à partir de vos étiquettes manuelles.
$res = $gallery->fineTune();
```

> Génère un coût réseau au premier appel (téléchargement des poids ResNet-50) et
> utilise `translate` pour la traduction française. Pour des raisons de performance,
> `aiTagAlbum` charge le modèle UNE seule fois pour tout le dossier.

---

## 8. Métadonnées et services

```php
// Localisation GPS (latitude / longitude).
$gallery->updateLocation('photos/a.jpg', 45.76, 4.83);

// Visibilité publique / licence.
$gallery->setPublic('photos/a.jpg', false);          // privée
$gallery->setLicense('photos/a.jpg', 'cc-by-sa');    // note : seule la chaîne est stockée

// Miniature (400x400 WebP dans <base>/thumbs/).
$gallery->generateThumbnail('photos/a.jpg');

// Liaison à un identifiant de message (forum).
$gallery->setMessageId('photos/a.jpg', 1234);
$img = $gallery->getByMessageId(1234);

// Suppression.
$gallery->deleteImage('photos/a.jpg');  // admin requis
$gallery->deleteByMessageId(1234);      // admin requis
```

---

## 9. Sécurité

- **Injection SQL** : le backend utilise des requêtes paramétrées, y compris pour
  la clause de visibilité (`user_tag` est toujours passé en paramètre).
- **Traversée de chemin** : tout chemin relatif est résolu et validé pour rester sous
  `photo_base_dir`. Une tentative `../../etc/passwd` est rejetée avec une erreur.
- **Visibilité** : `search`, `getAllImages`, `getGeolocated`, `getRandomImages`,
  `getAlbum`, `listAlbums` et `getAlbumFolderCover` respectent le contexte
  admin/membre.
- **Administration** : suppressions, visibilité, licence et liaison de message sont
  réservées aux admins (contrôlé côté backend à partir du drapeau `is_admin`).

---

## 10. Backend Python (utilisation avancée)

Les scripts `backend/` peuvent être appelés directement :

```bash
# API principale : <action> <db_path> <photo_base_dir> <is_admin> <user_tag> [args...]
python backend/api.py search /chemin/base.db /chemin/photos false null "plage"

# Auto-tagging : <action> <db_path> <photo_base_dir> <labels> <models_dir> <path>
python backend/auto_tagger.py tag_image base.db photos imagenet_classes.txt models "photos/a.jpg"

# Fine-tuning : <action> <db_path> <photo_base_dir> <is_admin> <user_tag> <models_dir>
python backend/fine_tune.py train base.db photos false null models
```

Toutes sortent un JSON sur stdout. En cas d'erreur, le backend renvoie
`{"success": false, "error": ...}` et, si la sortie n'est pas du JSON, la classe PHP
retourne le texte brut dans la clé `raw_output` pour faciliter le débogage.

---

## 11. Tests

```bash
python3 -m unittest discover -s tests -v
```

Les tests couvrent la visibilité (admin / membre / injecteur `user_tag`), la
protection contre la traversée de chemin, la recherche, la sélection aléatoire et
le cycle de vie des albums. Ils ne nécessitent aucune dépendance externe.
