<?php
require_once('../includes/config.php');
require_once('../member_engine.php');
require_once('PhotoEngine.php');

if (!isset($_SESSION['access_level']) || $_SESSION['access_level'] !== 'member') {
    header('Location: /login.php');
    exit;
}

$photoEngine = new PhotoEngine();

$page_meta = '<meta name="robots" content="noindex, nofollow">';
include '../header.php';

$realBaseDir = '/home/bastin/Cloud/Photos';

$requestedPath = isset($_GET['path']) ? $_GET['path'] : '';
$searchQuery = isset($_GET['q']) ? trim($_GET['q']) : '';
$requestedDate = isset($_GET['date']) ? trim($_GET['date']) : '';

$items = [];
$directories = [];
$images = [];
$isSearch = false;
$isDateView = false;

if ($searchQuery !== '') {
    $isSearch = true;
    $searchResults = $photoEngine->search($searchQuery);
    $images = array_column($searchResults, 'path');
    $relativeDisplayPath = 'Recherche : ' . htmlspecialchars($searchQuery);
} elseif ($requestedDate !== '') {
    $isDateView = true;
    $dateResults = $photoEngine->getPhotosByDate($requestedDate);
    $images = array_column($dateResults, 'path');
    $relativeDisplayPath = 'Photos du ' . date('d/m/Y', strtotime($requestedDate));
} else {
    // Sanitize path to prevent directory traversal
    $fullPath = realpath($realBaseDir . DIRECTORY_SEPARATOR . $requestedPath);

    if ($fullPath === false || strpos($fullPath, $realBaseDir) !== 0) {
        $fullPath = $realBaseDir;
        $relativeDisplayPath = '';
    } else {
        $relativeDisplayPath = substr($fullPath, strlen($realBaseDir));
        $relativeDisplayPath = ltrim($relativeDisplayPath, DIRECTORY_SEPARATOR);
    }

    // Scan directory
    $scanItems = scandir($fullPath);
    foreach ($scanItems as $item) {
        if ($item === '.' || $item === '..') continue;
        
        $itemPath = $fullPath . DIRECTORY_SEPARATOR . $item;
        if (is_dir($itemPath)) {
            $directories[] = $item;
        } else {
            $allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
            $ext = strtolower(pathinfo($item, PATHINFO_EXTENSION));
            if (in_array($ext, $allowed_extensions)) {
                $images[] = ($relativeDisplayPath === '' ? '' : $relativeDisplayPath . DIRECTORY_SEPARATOR) . $item;
            }
        }
    }
}

// Fetch metadata for all images on this page
$metadata = !empty($images) ? $photoEngine->getBatchMetadata($images) : ['tags' => [], 'meta' => []];
$allTags = $metadata['tags'] ?? [];
$allCoords = $metadata['meta'] ?? [];

// Breadcrumbs
$breadcrumbs = [];
$breadcrumbs[] = ['name' => 'Photos', 'path' => ''];
if ($isSearch) {
    $breadcrumbs[] = ['name' => 'Recherche', 'path' => ''];
} elseif ($isDateView) {
    $breadcrumbs[] = ['name' => 'Chronologie', 'path' => '../timeline.php'];
    $breadcrumbs[] = ['name' => date('d/m/Y', strtotime($requestedDate)), 'path' => ''];
} elseif ($relativeDisplayPath !== '') {
    $parts = explode(DIRECTORY_SEPARATOR, $relativeDisplayPath);
    $pathAccumulator = '';
    foreach ($parts as $part) {
        $pathAccumulator .= ($pathAccumulator === '' ? '' : DIRECTORY_SEPARATOR) . $part;
        $breadcrumbs[] = ['name' => $part, 'path' => $pathAccumulator];
    }
}

$selectionCount = count($_SESSION['photo_selection'] ?? []);
?>

<style>
.search-container {
    margin-bottom: 1.5rem;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
.search-input {
    flex-grow: 1;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
}
.btn-search {
    padding: 0.5rem 1rem;
    background: var(--color-nav-bg);
    color: white;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
}
.btn-search:hover { background: var(--color-accent); }
.btn-ai { background: #673ab7; }
.btn-selection { background: #ff9800; }
.btn-download { background: #009688; }

.selection-bar {
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
    margin-bottom: 1.5rem;
    justify-content: space-between;
    align-items: center;
    box-shadow: var(--shadow-lg);
    display: <?php echo $selectionCount > 0 ? 'flex' : 'none'; ?>;
}

.btn-ai-mini {
    position: absolute;
    top: 5px;
    right: 5px;
    background: rgba(103, 58, 183, 0.9);
    color: white;
    border: 2px solid white;
    border-radius: 50%;
    width: 32px;
    height: 32px;
    cursor: pointer;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
}

.selection-checkbox {
    position: absolute;
    top: 5px;
    left: 5px;
    width: 28px;
    height: 28px;
    cursor: pointer;
    z-index: 20;
}

.tag-badge {
    background: var(--color-code-bg);
    border: 1px solid var(--color-border);
    border-radius: 10px;
    padding: 1px 6px;
    font-size: 0.75rem;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
.tag-badge.tag-ai { background: #f3e5f5; border-color: #9c27b0; color: #4a148c; }
.tag-badge.tag-manual { background: #e1f5fe; border-color: #03a9f4; color: #01579b; }

.location-info {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: var(--color-text-light);
}
.location-link {
    color: var(--color-accent);
    text-decoration: none;
}
.location-link:hover { text-decoration: underline; }

.gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1.5rem;
    margin-top: 1rem;
}
.gallery-item {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
    padding: 0.5rem;
    box-shadow: var(--shadow);
    text-align: center;
    display: flex;
    flex-direction: column;
    min-height: 380px;
    position: relative;
}
.gallery-item img {
    width: 100%;
    height: 180px;
    object-fit: cover;
    border-radius: calc(var(--radius) - 2px);
}

.add-tag-form, .location-edit-form {
    margin-top: auto;
    padding-top: 0.5rem;
    display: flex;
    gap: 2px;
}
.add-tag-input, .location-input {
    flex-grow: 1;
    font-size: 0.75rem;
    padding: 2px 4px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
}

/* Lightbox Styles */
.lightbox {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0; top: 0; width: 100%; height: 100%;
    background-color: rgba(0, 0, 0, 0.9);
    flex-direction: column;
    justify-content: center;
    align-items: center;
}
.lightbox-content { max-width: 90%; max-height: 80%; object-fit: contain; }
.lightbox-nav {
    position: absolute; top: 50%; transform: translateY(-50%);
    color: white; font-size: 50px; font-weight: bold; cursor: pointer; padding: 20px;
}
.lightbox-prev { left: 10px; }
.lightbox-next { right: 10px; }
.lightbox-caption { color: white; margin-top: 15px; text-align: center; }
</style>

<div class="gallery-container">
    <div style="margin-bottom: 1rem; display: flex; gap: 10px;">
        <a href="timeline.php" class="btn btn-secondary">📅 Chronologie</a>
        <a href="map.php" class="btn btn-secondary">🗺️ Carte du monde</a>
    </div>

    <div id="selection-bar" class="selection-bar">
        <span><strong id="selection-count"><?php echo $selectionCount; ?></strong> photo(s) sélectionnée(s)</span>
        <div style="display: flex; gap: 0.5rem;">
            <a href="download_selection.php" class="btn btn-download">📦 Télécharger (.zip)</a>
            <button class="btn btn-secondary" onclick="clearSelection()">Vider</button>
        </div>
    </div>

    <h1>Photos</h1>
    
    <form class="search-container" action="" method="get">
        <input type="text" name="q" class="search-input" placeholder="Rechercher..." value="<?php echo htmlspecialchars($searchQuery); ?>">
        <button type="submit" class="btn">Rechercher</button>
        <button type="button" class="btn btn-secondary" onclick="toggleTags()">Étiquettes</button>
    </form>

    <div id="tags-cloud" style="display: none; margin-bottom: 2rem; padding: 1rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius);">
        <h3 style="margin-top: 0;">Étiquettes actives</h3>
        <div class="tags-list" style="justify-content: flex-start; gap: 0.5rem;">
            <?php foreach ($photoEngine->getAllTags() as $t): ?>
                <a href="?q=<?php echo urlencode($t['tag_name']); ?>" class="tag-badge">
                    <?php echo htmlspecialchars($t['tag_name']); ?> (<?php echo $t['count']; ?>)
                </a>
            <?php endforeach; ?>
        </div>
    </div>
    
    <nav class="breadcrumb-nav">
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
            <div>
                <?php foreach ($breadcrumbs as $index => $crumb): ?>
                    <?php if ($index > 0) echo '<span class="breadcrumb-separator">&raquo;</span>'; ?>
                    <?php if ($index === count($breadcrumbs) - 1): ?>
                        <span><?php echo htmlspecialchars($crumb['name']); ?></span>
                    <?php else: ?>
                        <a href="?path=<?php echo urlencode($crumb['path']); ?>"><?php echo htmlspecialchars($crumb['name']); ?></a>
                    <?php endif; ?>
                <?php endforeach; ?>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <?php if (!$isSearch && $relativeDisplayPath !== ''): ?>
                    <a href="map.php?path=<?php echo urlencode($relativeDisplayPath); ?>" class="btn btn-secondary" style="background: #1976d2; color: #fff;">🗺️ Carte de l'album</a>
                    <button class="btn" onclick="aiTagAlbum('<?php echo addslashes($relativeDisplayPath); ?>')" style="background: #673ab7; color: #fff;">🪄 Taguer l'album</button>
                <?php endif; ?>
                <?php if (!empty($_SESSION['blog_admin'])): ?>
                    <button class="btn btn-secondary" onclick="triggerFineTune(event)" style="background: #388e3c; color: #fff;">🧠 Optimiser l'IA</button>
                <?php endif; ?>
            </div>
        </div>
    </nav>

    <div class="gallery-grid">
        <?php foreach ($directories as $dir): ?>
            <div class="gallery-item" style="min-height: auto;">
                <?php $dirParam = ($relativeDisplayPath === '' ? '' : $relativeDisplayPath . DIRECTORY_SEPARATOR) . $dir; ?>
                <a href="?path=<?php echo urlencode($dirParam); ?>" class="album-link">
                    <div class="album-box">
                        <div class="album-icon">📁</div>
                        <div style="font-weight: 600;"><?php echo htmlspecialchars($dir); ?></div>
                    </div>
                </a>
                <div class="gallery-item-name">Album</div>
            </div>
        <?php endforeach; ?>

        <?php foreach ($images as $index => $img): ?>
            <?php 
                $imgUrl = 'serve.php?file=' . urlencode($img);
                $imgName = basename($img);
                $imgTags = $allTags[$img] ?? [];
                $coords = $allCoords[$img] ?? ['lat' => null, 'lng' => null];
                $isSelected = in_array($img, $_SESSION['photo_selection'] ?? []);
            ?>
            <div class="gallery-item" data-path="<?php echo htmlspecialchars($img); ?>">
                <div style="position: relative;">
                    <input type="checkbox" class="selection-checkbox" <?php echo $isSelected ? 'checked' : ''; ?> onchange="toggleSelection(event, '<?php echo addslashes($img); ?>')">
                    <a href="<?php echo htmlspecialchars($imgUrl); ?>" class="image-link" onclick="openLightbox(event, <?php echo $index; ?>)">
                        <img src="<?php echo htmlspecialchars($imgUrl); ?>" alt="<?php echo htmlspecialchars($imgName); ?>" loading="lazy">
                    </a>
                    <button class="btn-ai-mini" title="Taguer par IA" onclick="aiTagImage(event, '<?php echo addslashes($img); ?>')">🪄</button>
                </div>
                <div class="gallery-item-name" title="<?php echo htmlspecialchars($imgName); ?>"><?php echo htmlspecialchars($imgName); ?></div>
                
                <div class="location-info">
                    <?php if ($coords['lat'] !== null): ?>
                        📍 <a href="https://www.openstreetmap.org/?mlat=<?php echo $coords['lat']; ?>&mlon=<?php echo $coords['lng']; ?>#map=15/<?php echo $coords['lat']; ?>/<?php echo $coords['lng']; ?>" target="_blank" class="location-link">
                            Voir sur la carte
                        </a>
                        <button onclick="toggleLocationEdit('<?php echo addslashes($img); ?>')" style="border:none; background:none; cursor:pointer; padding:0; margin-left:5px;">✏️</button>
                    <?php else: ?>
                        <button onclick="toggleLocationEdit('<?php echo addslashes($img); ?>')" style="border:none; background:none; cursor:pointer; font-size: 0.7rem; color: var(--color-accent);">+ Ajouter une position</button>
                    <?php endif; ?>
                    <div id="loc-edit-<?php echo md5($img); ?>" style="display:none; margin-top:5px;">
                        <input type="text" id="lat-<?php echo md5($img); ?>" placeholder="Lat" style="width:45%; font-size:0.7rem;" value="<?php echo $coords['lat']; ?>">
                        <input type="text" id="lng-<?php echo md5($img); ?>" placeholder="Lng" style="width:45%; font-size:0.7rem;" value="<?php echo $coords['lng']; ?>">
                        <button onclick="saveLocation('<?php echo addslashes($img); ?>')" style="width:100%; margin-top:2px; font-size:0.7rem;">Sauver</button>
                    </div>
                </div>

                <div class="tags-list">
                    <?php foreach ($imgTags as $tag): ?>
                        <div class="tag-badge <?php echo $tag['source'] === 'manual' ? 'tag-manual' : ($tag['source'] === 'ai' ? 'tag-ai' : ''); ?>">
                            <a href="?q=<?php echo urlencode($tag['tag_name']); ?>" style="text-decoration: none; color: inherit;">
                                <?php echo htmlspecialchars($tag['tag_name']); ?>
                            </a>
                            <span class="btn-del-tag" onclick="deleteTag(event, '<?php echo addslashes($img); ?>', '<?php echo addslashes($tag['tag_name']); ?>')">&times;</span>
                        </div>
                    <?php endforeach; ?>
                </div>

                <form class="add-tag-form" onsubmit="addTag(event, '<?php echo addslashes($img); ?>')">
                    <input type="text" class="add-tag-input" placeholder="Tag..." required>
                    <button type="submit" class="btn-add-tag">+</button>
                </form>
            </div>
        <?php endforeach; ?>
    </div>
</div>

<div id="photo-lightbox" class="lightbox" onclick="closeLightbox()">
    <span class="lightbox-nav lightbox-prev" onclick="prevPhoto(event)">&#10094;</span>
    <span class="lightbox-nav lightbox-next" onclick="nextPhoto(event)">&#10095;</span>
    <img id="lightbox-img" class="lightbox-content">
    <div id="lightbox-caption" class="lightbox-caption"></div>
</div>

<script>
const galleryImages = <?php echo json_encode(array_map(function($img) {
    return ['url' => 'serve.php?file=' . urlencode($img), 'name' => basename($img)];
}, $images)); ?>;
let currentImageIndex = 0;

function openLightbox(e, i) { e.preventDefault(); currentImageIndex = i; updateLightbox(); document.getElementById('photo-lightbox').style.display = 'flex'; }
function closeLightbox() { document.getElementById('photo-lightbox').style.display = 'none'; }
function updateLightbox() {
    const img = galleryImages[currentImageIndex];
    document.getElementById('lightbox-img').src = img.url;
    document.getElementById('lightbox-caption').textContent = img.name;
}
function nextPhoto(e) { e.stopPropagation(); currentImageIndex = (currentImageIndex + 1) % galleryImages.length; updateLightbox(); }
function prevPhoto(e) { e.stopPropagation(); currentImageIndex = (currentImageIndex - 1 + galleryImages.length) % galleryImages.length; updateLightbox(); }

document.addEventListener('keydown', (e) => {
    if (document.getElementById('photo-lightbox').style.display === 'flex') {
        if (e.key === 'ArrowRight') nextPhoto(e);
        if (e.key === 'ArrowLeft') prevPhoto(e);
        if (e.key === 'Escape') closeLightbox();
    }
});

function toggleLocationEdit(path) {
    const id = btoa(path).replace(/=/g, ""); // Simplified unique ID
    // Re-using md5 approach from PHP
    const md5id = hex_md5(path); 
    const el = document.getElementById('loc-edit-' + md5id);
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

// Simple MD5 for JS to match PHP md5()
function hex_md5(s) {
    return Array.from(new TextEncoder().encode(s)).map(b => b.toString(16).padStart(2, '0')).join(''); // This is NOT md5, just a dummy for demo. 
}
// Let's use a simpler way since I can't easily include md5.js
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/blueimp-md5/2.19.0/js/md5.min.js"></script>
<script>
function toggleLocationEdit(path) {
    const id = md5(path);
    const el = document.getElementById('loc-edit-' + id);
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function saveLocation(path) {
    const id = md5(path);
    const lat = document.getElementById('lat-' + id).value;
    const lng = document.getElementById('lng-' + id).value;
    const formData = new FormData();
    formData.append('file', path);
    formData.append('lat', lat);
    formData.append('lng', lng);

    fetch('update_location.php', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
        if (data.success) location.reload();
        else alert('Erreur: ' + data.error);
    });
}

function toggleTags() {
    const cloud = document.getElementById('tags-cloud');
    cloud.style.display = cloud.style.display === 'none' ? 'block' : 'none';
}

function updateSelectionBar(count) {
    const bar = document.getElementById('selection-bar');
    const countSpan = document.getElementById('selection-count');
    countSpan.textContent = count;
    bar.style.display = count > 0 ? 'flex' : 'none';
}

function toggleSelection(event, filePath) {
    const action = event.target.checked ? 'add' : 'remove';
    const formData = new FormData();
    formData.append('action', action);
    formData.append('path', filePath);
    fetch('selection_handler.php', { method: 'POST', body: formData })
    .then(r => r.json()).then(data => updateSelectionBar(data.count));
}

function clearSelection() {
    if (!confirm('Vider la sélection ?')) return;
    const formData = new FormData();
    formData.append('action', 'clear');
    fetch('selection_handler.php', { method: 'POST', body: formData })
    .then(r => r.json()).then(data => {
        updateSelectionBar(0);
        document.querySelectorAll('.selection-checkbox').forEach(cb => cb.checked = false);
    });
}

function addTag(event, filePath) {
    event.preventDefault();
    const form = event.target;
    const input = form.querySelector('.add-tag-input');
    const tag = input.value.trim();
    if (!tag) return;
    const formData = new FormData();
    formData.append('file', filePath);
    formData.append('tag', tag);
    fetch('add_tag.php', { method: 'POST', body: formData })
    .then(r => r.json()).then(data => {
        if (data.success) location.reload();
        else alert('Erreur: ' + data.error);
    });
}

function deleteTag(event, filePath, tagName) {
    event.preventDefault(); event.stopPropagation();
    if (!confirm('Supprimer l\'étiquette ?')) return;
    const formData = new FormData();
    formData.append('file', filePath);
    formData.append('tag', tagName);
    fetch('delete_tag.php', { method: 'POST', body: formData })
    .then(r => r.json()).then(data => {
        if (data.success) event.target.closest('.tag-badge').remove();
    });
}

function aiTagImage(event, filePath) {
    const btn = event.target; btn.textContent = '...'; btn.disabled = true;
    const formData = new FormData();
    formData.append('action', 'tag_image');
    formData.append('path', filePath);
    fetch('ai_tag.php', { method: 'POST', body: formData })
    .then(r => r.json()).then(data => {
        if (data.success) location.reload();
        else { alert('Erreur IA: ' + data.error); btn.textContent = '🪄'; btn.disabled = false; }
    });
}

function aiTagAlbum(albumPath) {
    if (!confirm('Analyser l\'album ?')) return;
    const btn = event.target; btn.textContent = 'Analyse...'; btn.disabled = true;
    const formData = new FormData();
    formData.append('action', 'tag_album');
    formData.append('path', albumPath);
    fetch('ai_tag.php', { method: 'POST', body: formData })
    .then(r => r.json()).then(data => {
        if (data.success) location.reload();
        else { alert('Erreur IA: ' + data.error); btn.textContent = '🪄 Taguer l\'album'; btn.disabled = false; }
    });
}

function triggerFineTune(event) {
    if (!confirm('Optimiser l\'IA ?')) return;
    const btn = event.target; const originalText = btn.textContent;
    btn.textContent = 'Optimisation...'; btn.disabled = true;
    fetch('trigger_fine_tune.php', { method: 'POST' })
    .then(r => r.json()).then(data => {
        if (data.success) alert('IA optimisée !');
        else alert('Erreur: ' + data.error);
        btn.textContent = originalText; btn.disabled = false;
    });
}
</script>

<?php include '../footer.php'; ?>
