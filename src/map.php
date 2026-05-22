<?php
require_once('../includes/config.php');
require_once('../member_engine.php');
require_once('PhotoEngine.php');

if (!isset($_SESSION['access_level']) || $_SESSION['access_level'] !== 'member') {
    header('Location: /login.php');
    exit;
}

$photoEngine = new PhotoEngine();

$filterPath = $_GET['path'] ?? '';
$filterSearch = $_GET['q'] ?? '';

$page_meta = '<meta name="robots" content="noindex, nofollow">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />';
include '../header.php';

if ($filterSearch !== '') {
    $results = $photoEngine->search($filterSearch);
    // Search returns full info including lat/lng now
    $geolocated = array_filter($results, function($r) { return $r['lat'] !== null; });
    $title = "Carte : Recherche '$filterSearch'";
} elseif ($filterPath !== '') {
    // We don't have a direct "get geolocated by path" yet, 
    // but we can just filter all geolocated ones
    $all = $photoEngine->getGeolocated();
    $geolocated = array_filter($all, function($p) use ($filterPath) {
        return strpos($p['path'], $filterPath) === 0;
    });
    $title = "Carte de l'album : " . htmlspecialchars($filterPath);
} else {
    $geolocated = $photoEngine->getGeolocated();
    $title = "Carte du Monde";
}
?>

<style>
#map {
    height: 700px;
    width: 100%;
    border-radius: var(--radius);
    border: 1px solid var(--color-border);
    box-shadow: var(--shadow);
}
.map-popup img {
    max-width: 150px;
    border-radius: 4px;
    margin-bottom: 5px;
}
</style>

<div class="gallery-container">
    <div style="margin-bottom: 1rem; display: flex; gap: 10px;">
        <a href="index.php" class="btn btn-secondary">🏠 Galerie</a>
        <a href="timeline.php" class="btn btn-secondary">📅 Chronologie</a>
        <a href="map.php" class="btn btn-secondary">🗺️ Carte du monde</a>
    </div>

    <h1><?php echo $title; ?></h1>
    <p><?php echo count($geolocated); ?> photo(s) affichée(s) sur la carte.</p>
    
    <div id="map"></div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
<script>
const map = L.map('map').setView([20, 0], 2);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

const markers = L.markerClusterGroup();
const photos = <?php echo json_encode($geolocated); ?>;

photos.forEach(p => {
    if (p.lat && p.lng) {
        const marker = L.marker([p.lat, p.lng]);
        const popupContent = `
            <div class="map-popup">
                <a href="index.php?path=${encodeURIComponent(p.path.substring(0, p.path.lastIndexOf('/')))}">
                    <img src="serve.php?file=${encodeURIComponent(p.path)}" loading="lazy">
                </a><br>
                <strong>${p.name}</strong><br>
                <a href="index.php?path=${encodeURIComponent(p.path.substring(0, p.path.lastIndexOf('/')))}">Voir l'album</a>
            </div>
        `;
        marker.bindPopup(popupContent);
        markers.addLayer(marker);
    }
});

map.addLayer(markers);

// Adjust view to fit all markers if some exist
if (photos.length > 0) {
    const group = new L.featureGroup(markers.getLayers());
    if (markers.getLayers().length > 0) {
        map.fitBounds(markers.getBounds());
    }
}
</script>

<?php include '../footer.php'; ?>
