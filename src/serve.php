<?php
/**
 * SlashGallery - Serve file endpoint (images + videos)
 *
 * Serves a media file (photo or video) from the gallery base directory, with
 * support for MIME detection and HTTP Range requests so that <video> seeking /
 * streaming works.
 *
 * Expected GET parameter:
 *   - file: relative path of the media file to serve
 *
 * The hosting application should include this file or copy it to the
 * appropriate location, ensuring that:
 *   1. A session is active and the user is authenticated (auth is left to the
 *      hosting application)
 *   2. $gallery is an instance of SlashGallery with proper config
 *
 * Example integration:
 *   require_once 'SlashGallery.php';
 *   $gallery = new SlashGallery($config);
 *   $gallery->setSecurityContext($isAdmin, $userTag);
 *   require 'serve.php';
 */

if (!isset($gallery) || !($gallery instanceof SlashGallery)) {
    header('HTTP/1.0 500 Internal Server Error');
    exit;
}

$config = $gallery->getConfig();
$realBaseDir = rtrim($config['photo_base_dir'], '/\\');

$file = $_GET['file'] ?? '';
if (empty($file)) {
    header('HTTP/1.0 400 Bad Request');
    exit;
}

// Normalize path and check it's within the base directory
$fullPath = realpath($realBaseDir . DIRECTORY_SEPARATOR . $file);

if ($fullPath === false || strpos($fullPath, $realBaseDir . DIRECTORY_SEPARATOR) !== 0) {
    header('HTTP/1.0 403 Forbidden');
    exit;
}

if (!is_file($fullPath)) {
    header('HTTP/1.0 404 Not Found');
    exit;
}

// Allowed photo and video extensions with their MIME types.
$allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
$video_extensions = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', 'wmv', '3gp', 'mpg', 'mpeg'];
$mime_map = [
    'jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'png' => 'image/png',
    'gif' => 'image/gif', 'webp' => 'image/webp',
    'mp4' => 'video/mp4', 'mov' => 'video/quicktime', 'avi' => 'video/x-msvideo',
    'mkv' => 'video/x-matroska', 'webm' => 'video/webm', 'm4v' => 'video/mp4',
    'wmv' => 'video/x-ms-wmv', '3gp' => 'video/3gpp', 'mpg' => 'video/mpeg',
    'mpeg' => 'video/mpeg',
];
$ext = strtolower(pathinfo($fullPath, PATHINFO_EXTENSION));
$mime = isset($mime_map[$ext]) ? $mime_map[$ext] : @finfo_file(finfo_open(FILEINFO_MIME_TYPE), $fullPath);

if (!in_array($ext, $allowed_extensions) && !in_array($ext, $video_extensions)) {
    header('HTTP/1.0 403 Forbidden');
    exit;
}

$size = filesize($fullPath);

// Support HTTP Range requests so video seeking / streaming works.
$range = isset($_SERVER['HTTP_RANGE']) ? $_SERVER['HTTP_RANGE'] : '';
if ($range && preg_match('/bytes=(\d*)-(\d*)/', $range, $m)) {
    $start = $m[1] !== '' ? (int)$m[1] : 0;
    $end = $m[2] !== '' ? (int)$m[2] : $size - 1;
    if ($start > $end || $end >= $size) {
        header('HTTP/1.1 416 Requested Range Not Satisfiable');
        header('Content-Range: bytes */' . $size);
        exit;
    }
    header('HTTP/1.1 206 Partial Content');
    header("Content-Range: bytes $start-$end/$size");
    header('Content-Length: ' . ($end - $start + 1));
    header('Content-Type: ' . $mime);
    header('Accept-Ranges: bytes');
    $fp = fopen($fullPath, 'rb');
    fseek($fp, $start);
    $remaining = $end - $start + 1;
    while ($remaining > 0 && !feof($fp)) {
        $chunk = fread($fp, min(1024 * 1024, $remaining));
        if ($chunk === false) break;
        echo $chunk;
        $remaining -= strlen($chunk);
    }
    fclose($fp);
    exit;
}

header('Accept-Ranges: bytes');
header('Content-Type: ' . $mime);
header('Content-Length: ' . $size);
readfile($fullPath);
exit;
