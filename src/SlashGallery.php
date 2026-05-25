<?php

/**
 * SlashGallery Reusable Library
 * Standalone photo gallery system with AI tagging, search, and maps.
 */
class SlashGallery {
    private $config;
    private $pythonVenv;
    private $backendDir;
    private $isAdmin = false;
    private $userTag = null;

    public function __construct($config) {
        $this->config = array_merge([
            'db_path' => '',
            'photo_base_dir' => '',
            'python_venv' => '',
            'backend_dir' => __DIR__ . '/../backend',
            'base_url' => '/photos/',
            'labels_path' => __DIR__ . '/../imagenet_classes.txt',
            'models_dir' => __DIR__ . '/../models'
        ], $config);

        $this->pythonVenv = $this->config['python_venv'] . '/bin/python';
        $this->backendDir = $this->config['backend_dir'];
        
        if (!is_dir($this->config['models_dir'])) {
            mkdir($this->config['models_dir'], 0755, true);
        }
    }

    public function setSecurityContext($isAdmin, $userTag = null) {
        $this->isAdmin = $isAdmin;
        $this->userTag = $userTag;
    }

    private function runPython($script, $action, ...$args) {
        $scriptPath = $this->backendDir . '/' . $script;
        $cmd = escapeshellarg($this->pythonVenv) . " " . escapeshellarg($scriptPath) . " " . escapeshellarg($action);
        
        $cmd .= " " . escapeshellarg($this->config['db_path']);
        $cmd .= " " . escapeshellarg($this->config['photo_base_dir']);
        $cmd .= " " . escapeshellarg($this->isAdmin ? 'true' : 'false');
        $cmd .= " " . escapeshellarg($this->userTag ?? 'null');

        foreach ($args as $arg) {
            $cmd .= " " . escapeshellarg($arg);
        }
        $cmd .= " 2>/dev/null";
        $output = shell_exec($cmd);
        return json_decode($output, true);
    }

    public function getTimeline() {
        return $this->runPython('api.py', 'get_summarized_timeline');
    }

    public function getPhotosByDate($date) {
        return $this->runPython('api.py', 'get_photos_by_date', $date);
    }

    public function getGeolocated() {
        return $this->runPython('api.py', 'get_geolocated');
    }

    public function search($query, $filterTag = null) {
        return $this->runPython('api.py', 'search', $filterTag ?? 'null', $query);
    }

    public function getAllImages($filterTag = null) {
        return $this->runPython('api.py', 'get_all_images', $filterTag ?? 'null');
    }

    public function getByMessageId($msgId) {
        return $this->runPython('api.py', 'get_by_message_id', $msgId);
    }

    public function getAllTags() {
        return $this->runPython('api.py', 'get_all_tags');
    }

    public function getBatchMetadata($filePaths) {
        return $this->runPython('api.py', 'get_batch_metadata', json_encode($filePaths));
    }

    public function addTag($filePath, $tag) {
        return $this->runPython('api.py', 'add_tag', $filePath, $tag);
    }

    public function deleteTag($filePath, $tag) {
        return $this->runPython('api.py', 'delete_tag', $filePath, $tag);
    }

    public function setMessageId($filePath, $msgId) {
        return $this->runPython('api.py', 'set_message_id', $filePath, $msgId);
    }

    public function deleteByMessageId($msgId) {
        return $this->runPython('api.py', 'delete_by_message_id', $msgId);
    }

    public function updateLocation($filePath, $lat, $lng) {
        return $this->runPython('api.py', 'update_location', $filePath, $lat === null ? 'null' : $lat, $lng === null ? 'null' : $lng);
    }

    public function setPublic($filePath, $isPublic) {
        return $this->runPython('api.py', 'set_public', $filePath, $isPublic ? 'true' : 'false');
    }

    public function deleteImage($filePath) {
        return $this->runPython('api.py', 'delete_image', $filePath);
    }

    public function generateThumbnail($filePath) {
        return $this->runPython('api.py', 'generate_thumbnail', $filePath);
    }

    public function aiTagImage($filePath) {
        $scriptPath = $this->backendDir . '/auto_tagger.py';
        $cmd = escapeshellarg($this->pythonVenv) . " " . escapeshellarg($scriptPath) . " tag_image";
        $cmd .= " " . escapeshellarg($this->config['db_path']);
        $cmd .= " " . escapeshellarg($this->config['photo_base_dir']);
        $cmd .= " " . escapeshellarg($this->config['labels_path']);
        $cmd .= " " . escapeshellarg($this->config['models_dir']);
        $cmd .= " " . escapeshellarg($filePath);
        $cmd .= " 2>/dev/null";
        $output = shell_exec($cmd);
        return json_decode($output, true);
    }

    public function aiTagAlbum($albumPath) {
        $scriptPath = $this->backendDir . '/auto_tagger.py';
        $cmd = escapeshellarg($this->pythonVenv) . " " . escapeshellarg($scriptPath) . " tag_album";
        $cmd .= " " . escapeshellarg($this->config['db_path']);
        $cmd .= " " . escapeshellarg($this->config['photo_base_dir']);
        $cmd .= " " . escapeshellarg($this->config['labels_path']);
        $cmd .= " " . escapeshellarg($this->config['models_dir']);
        $cmd .= " " . escapeshellarg($albumPath);
        $cmd .= " 2>/dev/null";
        $output = shell_exec($cmd);
        return json_decode($output, true);
    }

    public function fineTune() {
        return $this->runPython('fine_tune.py', 'train');
    }
}
?>
