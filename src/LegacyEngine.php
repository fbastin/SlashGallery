<?php
class PhotoEngine {
    private $pythonScript;
    private $autoTaggerScript;
    private $venvPython;

    public function __construct() {
        $this->pythonScript = __DIR__ . '/photo_db_helper.py';
        $this->autoTaggerScript = __DIR__ . '/auto_tagger.py';
        $this->venvPython = __DIR__ . '/venv/bin/python';
    }

    private function runPython($script, $action, ...$args) {
        $cmd = escapeshellarg($this->venvPython) . " " . escapeshellarg($script) . " " . escapeshellarg($action);
        foreach ($args as $arg) {
            $cmd .= " " . escapeshellarg($arg);
        }
        $cmd .= " 2>/dev/null";
        $output = shell_exec($cmd);
        return json_decode($output, true);
    }

    public function search($query) {
        $results = $this->runPython($this->pythonScript, 'search', $query) ?: [];
        // Extract paths for backward compatibility if needed, 
        // but it's better to keep the full info
        return $results;
    }

    public function getAllTags() {
        return $this->runPython($this->pythonScript, 'get_all_tags') ?: [];
    }

    public function getTags($filePath) {
        return $this->runPython($this->pythonScript, 'get_tags', $filePath) ?: [];
    }

    public function getBatchMetadata($filePaths) {
        return $this->runPython($this->pythonScript, 'get_batch_metadata', json_encode($filePaths)) ?: [];
    }

    public function getTimeline() {
        return $this->runPython($this->pythonScript, 'get_timeline') ?: [];
    }

    public function getGeolocated() {
        return $this->runPython($this->pythonScript, 'get_geolocated') ?: [];
    }

    public function updateLocation($filePath, $lat, $lng) {
        return $this->runPython($this->pythonScript, 'update_location', $filePath, $lat === null ? 'null' : $lat, $lng === null ? 'null' : $lng);
    }

    public function addTag($filePath, $tagName) {
        return $this->runPython($this->pythonScript, 'add_tag', $filePath, $tagName);
    }

    public function deleteTag($filePath, $tagName) {
        return $this->runPython($this->pythonScript, 'delete_tag', $filePath, $tagName);
    }

    public function aiTagImage($filePath) {
        return $this->runPython($this->autoTaggerScript, 'tag_image', $filePath);
    }

    public function aiTagAlbum($albumPath) {
        return $this->runPython($this->autoTaggerScript, 'tag_album', $albumPath);
    }

    public function fineTune() {
        return $this->runPython(__DIR__ . '/fine_tune.py', 'train');
    }
}
