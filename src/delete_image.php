<?php
/**
 * SlashGallery - Delete image endpoint
 *
 * Expected POST parameters:
 *   - file: relative path of the image to delete
 *
 * The hosting application should include this file or copy it to the
 * appropriate location, ensuring that:
 *   1. A session is active and the user is authenticated
 *   2. $gallery is an instance of SlashGallery with proper config
 *
 * Example integration:
 *   require_once 'SlashGallery.php';
 *   $gallery = new SlashGallery($config);
 *   require 'delete_image.php';
 */

header('Content-Type: application/json');

if (!isset($gallery) || !($gallery instanceof SlashGallery)) {
    echo json_encode(['success' => false, 'error' => 'Gallery not initialized']);
    exit;
}

$file = $_POST['file'] ?? '';
if (empty($file)) {
    echo json_encode(['success' => false, 'error' => 'No file specified']);
    exit;
}

echo json_encode($gallery->deleteImage($file));
