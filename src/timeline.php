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

$timeline = $photoEngine->getTimeline();
?>

<style>
.timeline-container {
    max-width: 800px;
    margin: 2rem auto;
}
.timeline-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.2s;
}
.timeline-item:hover {
    background: var(--color-code-bg);
}
.timeline-date {
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--color-accent);
}
.timeline-count {
    background: var(--color-nav-bg);
    color: white;
    padding: 0.2rem 0.8rem;
    border-radius: 20px;
    font-size: 0.8rem;
}
.year-header {
    margin-top: 3rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--color-nav-bg);
    color: var(--color-nav-bg);
}
.timeline-nav {
    position: sticky;
    top: 4rem; /* Below the sticky main menu */
    z-index: 90;
    background: var(--color-surface);
    padding: 0.75rem;
    border-radius: var(--radius);
    border: 1px solid var(--color-border);
    margin-bottom: 2rem;
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    box-shadow: var(--shadow-lg);
}
</style>

<div class="gallery-container">
    <div style="margin-bottom: 1rem; display: flex; gap: 10px;">
        <a href="index.php" class="btn btn-secondary">🏠 Galerie</a>
        <a href="timeline.php" class="btn btn-secondary">📅 Chronologie</a>
        <a href="map.php" class="btn btn-secondary">🗺️ Carte du monde</a>
    </div>

    <h1>Ordre Chronologique</h1>
    <p>Sélectionnez une date pour voir les photos correspondantes.</p>
    
    <div class="timeline-nav">
        <?php 
        $years = [];
        foreach($timeline as $t) {
            $y = date('Y', strtotime($t['day']));
            if (!in_array($y, $years)) $years[] = $y;
        }
        foreach($years as $year): ?>
            <a href="#year-<?php echo $year; ?>" class="btn btn-secondary" style="font-size: 0.8rem;"><?php echo $year; ?></a>
        <?php endforeach; ?>
    </div>

    <div class="timeline-container">
        <?php 
        $currentYear = "";
        foreach ($timeline as $t): 
            $year = date('Y', strtotime($t['day']));
            if ($year !== $currentYear): 
                $currentYear = $year;
        ?>
            <h2 id="year-<?php echo $year; ?>" class="year-header"><?php echo $year; ?></h2>
        <?php endif; ?>
            
            <a href="index.php?date=<?php echo urlencode($t['day']); ?>" style="text-decoration: none; color: inherit;">
                <div class="timeline-item">
                    <div class="timeline-date">
                        <?php 
                        setlocale(LC_TIME, 'fr_FR.UTF-8', 'fra');
                        echo strftime('%d %B %Y', strtotime($t['day'])); 
                        ?>
                    </div>
                    <div class="timeline-count"><?php echo $t['count']; ?> photo(s)</div>
                </div>
            </a>
        <?php endforeach; ?>
    </div>
</div>

<?php include '../footer.php'; ?>
