<?php

/**
 * SlashGallery Reusable Library
 * Standalone photo gallery system with AI tagging, search, and maps.
 */
class SlashGallery {
    private $config;
    private $pythonVenv;
    private $backendDir;

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

    private function runPython($script, $action, ...$args) {
        $scriptPath = $this->backendDir . '/' . $script;
        $cmd = escapeshellarg($this->pythonVenv) . " " . escapeshellarg($scriptPath) . " " . escapeshellarg($action);
        foreach ($args as $arg) {
            $cmd .= " " . escapeshellarg($arg);
        }
        $cmd .= " 2>/dev/null";
        $output = shell_exec($cmd);
        return json_decode($output, true);
    }

    public function getTimeline() {
        return $this->runPython('api.py', 'get_summarized_timeline', $this->config['db_path'], $this->config['photo_base_dir']);
    }

    public function getPhotosByDate($date) {
        return $this->runPython('api.py', 'get_photos_by_date', $this->config['db_path'], $this->config['photo_base_dir'], $date);
    }

    public function getGeolocated() {
        return $this->runPython('api.py', 'get_geolocated', $this->config['db_path'], $this->config['photo_base_dir']);
    }

    public function search($query) {
        return $this->runPython('api.py', 'search', $this->config['db_path'], $this->config['photo_base_dir'], $query);
    }

    public function getAllTags() {
        return $this->runPython('api.py', 'get_all_tags', $this->config['db_path'], $this->config['photo_base_dir']);
    }

    public function getBatchMetadata($filePaths) {
        return $this->runPython('api.py', 'get_batch_metadata', $this->config['db_path'], $this->config['photo_base_dir'], json_encode($filePaths));
    }

    public function addTag($filePath, $tag) {
        return $this->runPython('api.py', 'add_tag', $this->config['db_path'], $this->config['photo_base_dir'], $filePath, $tag);
    }

    public function deleteTag($filePath, $tag) {
        return $this->runPython('api.py', 'delete_tag', $this->config['db_path'], $this->config['photo_base_dir'], $filePath, $tag);
    }

    public function updateLocation($filePath, $lat, $lng) {
        return $this->runPython('api.py', 'update_location', $this->config['db_path'], $this->config['photo_base_dir'], $filePath, $lat === null ? 'null' : $lat, $lng === null ? 'null' : $lng);
    }

    public function aiTagImage($filePath) {
        return $this->runPython('auto_tagger.py', 'tag_image', 
            $this->config['db_path'], 
            $this->config['photo_base_dir'], 
            $this->config['labels_path'], 
            $this->config['models_dir'], 
            $filePath
        );
    }

    public function aiTagAlbum($albumPath) {
        return $this->runPython('auto_tagger.py', 'tag_album', 
            $this->config['db_path'], 
            $this->config['photo_base_dir'], 
            $this->config['labels_path'], 
            $this->config['models_dir'], 
            $albumPath
        );
    }

    public function fineTune() {
        return $this->runPython('fine_tune.py', 'train');
    }
}
