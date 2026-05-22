import sys
import torch
import torch.nn as nn
import json
import os
import sqlite3
import warnings
from datetime import datetime
from torchvision import models, transforms
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from translate import Translator

# Suppress warnings to avoid breaking JSON output
warnings.filterwarnings("ignore")

# Path configuration
DB_PATH = '/home/bastin/Cloud/Photos/photo_catalog.db'
PHOTO_BASE_DIR = '/home/bastin/Cloud/Photos'
LABELS_PATH = '/var/www/slashbin.net/photos/imagenet_classes.txt'
MODEL_DIR = '/var/www/slashbin.net/photos/models'

# Set Torch home to use our local models directory
os.environ['TORCH_HOME'] = MODEL_DIR

# Initialize translator
translator = Translator(to_lang="fr", from_lang="en")

# Path for custom model
CUSTOM_MODEL_PATH = '/var/www/slashbin.net/photos/models/custom_resnet50.pth'
LABEL_MAP_PATH = '/var/www/slashbin.net/photos/models/custom_labels.json'

# Load labels
with open(LABELS_PATH, 'r') as f:
    LABELS = [line.strip() for line in f.readlines()]

# Global models cache
IMAGE_NET_MODEL = None
CUSTOM_MODEL = None
CUSTOM_LABELS = None

def get_models():
    global IMAGE_NET_MODEL, CUSTOM_MODEL, CUSTOM_LABELS
    if IMAGE_NET_MODEL is None:
        IMAGE_NET_MODEL = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        IMAGE_NET_MODEL.eval()
    
    if CUSTOM_MODEL is None and os.path.exists(CUSTOM_MODEL_PATH) and os.path.exists(LABEL_MAP_PATH):
        try:
            with open(LABEL_MAP_PATH, 'r') as f:
                CUSTOM_LABELS = json.load(f)
            
            CUSTOM_MODEL = models.resnet50()
            num_ftrs = CUSTOM_MODEL.fc.in_features
            CUSTOM_MODEL.fc = nn.Linear(num_ftrs, len(CUSTOM_LABELS))
            CUSTOM_MODEL.load_state_dict(torch.load(CUSTOM_MODEL_PATH))
            CUSTOM_MODEL.eval()
        except:
            CUSTOM_MODEL = None
            
    return IMAGE_NET_MODEL, CUSTOM_MODEL, CUSTOM_LABELS

preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def get_gps_info(exif_data):
    gps_info = {}
    if not exif_data:
        return None
    for tag, value in exif_data.items():
        decoded = TAGS.get(tag, tag)
        if decoded == "GPSInfo":
            for t in value:
                sub_decoded = GPSTAGS.get(t, t)
                gps_info[sub_decoded] = value[t]
    return gps_info

def get_decimal_from_obj(res, ref):
    if not res or not ref:
        return None
    try:
        d = float(res[0])
        m = float(res[1])
        s = float(res[2])
        decimal = d + (m / 60.0) + (s / 3600.0)
        if ref in ['S', 'W']:
            decimal = -decimal
        return decimal
    except:
        return None

def get_exif_location(full_path):
    try:
        with Image.open(full_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None, None
            gps_info = get_gps_info(exif_data)
            if not gps_info:
                return None, None
            lat = get_decimal_from_obj(gps_info.get('GPSLatitude'), gps_info.get('GPSLatitudeRef'))
            lng = get_decimal_from_obj(gps_info.get('GPSLongitude'), gps_info.get('GPSLongitudeRef'))
            return lat, lng
    except:
        return None, None

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def translate_tag(tag_en):
    try:
        main_tag = tag_en.split(',')[0]
        return translator.translate(main_tag).lower()
    except:
        return None

def auto_tag_image(image_rel_path, threshold=20.0):
    full_path = os.path.join(PHOTO_BASE_DIR, image_rel_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": "File not found"}

    # Extract EXIF location
    lat, lng = get_exif_location(full_path)

    try:
        img = Image.open(full_path).convert('RGB')
        img_t = preprocess(img)
        batch_t = torch.unsqueeze(img_t, 0)

        imagenet_model, custom_model, custom_labels = get_models()
        
        all_detected_en = set()

        # 1. ImageNet detection
        with torch.no_grad():
            out = imagenet_model(batch_t)
            probabilities = torch.nn.functional.softmax(out, dim=1)[0] * 100
            for i in range(len(probabilities)):
                if probabilities[i] > threshold:
                    all_detected_en.add(LABELS[i].lower())
            if not all_detected_en:
                _, index = torch.max(out, 1)
                all_detected_en.add(LABELS[index[0]].lower())

        # 2. Custom model detection
        if custom_model:
            with torch.no_grad():
                out = custom_model(batch_t)
                probabilities = torch.sigmoid(out)[0] * 100
                for i in range(len(probabilities)):
                    if probabilities[i] > threshold:
                        all_detected_en.add(custom_labels[i].lower())

        # Translate and prepare final list
        all_tags = []
        for tag_en in all_detected_en:
            all_tags.append(tag_en)
            tag_fr = translate_tag(tag_en)
            if tag_fr and tag_fr != tag_en:
                all_tags.append(tag_fr)

        # Save to database
        conn = get_db_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM images WHERE file_path = ?", (full_path,))
        row = cursor.fetchone()
        if not row:
            stats = os.stat(full_path)
            cursor.execute(
                "INSERT INTO images (file_path, file_name, date_added, file_size, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (full_path, os.path.basename(full_path), datetime.now(), stats.st_size, lat, lng)
            )
            image_id = cursor.lastrowid
        else:
            image_id = row['id']
            if lat is not None:
                cursor.execute("UPDATE images SET latitude = ?, longitude = ? WHERE id = ?", (lat, lng, image_id))

        for tag in all_tags:
            cursor.execute("SELECT id FROM tags WHERE image_id = ? AND tag_name = ? AND source = 'ai'", (image_id, tag))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO tags (image_id, tag_name, source) VALUES (?, ?, 'ai')",
                    (image_id, tag)
                )
        
        conn.commit()
        conn.close()
        return {"success": True, "tags": list(all_tags)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def process_album(album_rel_path):
    full_album_path = os.path.join(PHOTO_BASE_DIR, album_rel_path)
    if not os.path.isdir(full_album_path):
        return {"success": False, "error": "Not a directory"}
    
    count = 0
    errors = []
    for item in os.listdir(full_album_path):
        if item.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            res = auto_tag_image(os.path.join(album_rel_path, item))
            if res['success']:
                count += 1
            else:
                errors.append(f"{item}: {res['error']}")
    
    return {"success": True, "processed": count, "errors": errors}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"success": False, "error": "Usage: action path"}))
        sys.exit(1)
        
    action = sys.argv[1]
    path = sys.argv[2]
    
    if action == "tag_image":
        print(json.dumps(auto_tag_image(path)))
    elif action == "tag_album":
        print(json.dumps(process_album(path)))
