import os
import sys
import sqlite3
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from PIL import Image
import json
from datetime import datetime

# Configuration (overridable via command-line args)
DB_PATH = None
PHOTO_BASE_DIR = None
CUSTOM_MODEL_PATH = None
LABEL_MAP_PATH = None
MODEL_DIR = None

class PhotoDataset(Dataset):
    def __init__(self, image_paths, labels, label_to_idx, transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.label_to_idx = label_to_idx
        self.transform = transform
        self.num_classes = len(label_to_idx)

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        try:
            img_path = self.image_paths[idx]
            image = Image.open(img_path).convert('RGB')
            if self.transform:
                image = self.transform(image)
            
            # Create multi-hot label vector
            target = torch.zeros(self.num_classes)
            for label in self.labels[idx]:
                if label in self.label_to_idx:
                    target[self.label_to_idx[label]] = 1.0
            
            return image, target
        except Exception as e:
            # Return a dummy if image is corrupted
            return torch.zeros(3, 224, 224), torch.zeros(self.num_classes)

def train_model(epochs=5, batch_size=8, lr=0.001):
    os.environ['TORCH_HOME'] = MODEL_DIR
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Get all images with manual tags
    cursor.execute("""
        SELECT i.file_path, GROUP_CONCAT(t.tag_name) as tags
        FROM images i
        JOIN tags t ON i.id = t.image_id
        WHERE t.source = 'manual'
        GROUP BY i.id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"success": False, "error": "No manual tags found to train on."}

    image_paths = []
    image_labels = []
    unique_tags = set()

    base = os.path.normpath(PHOTO_BASE_DIR)

    def _resolve(path):
        if os.path.isabs(path):
            candidate = os.path.normpath(path)
        else:
            candidate = os.path.normpath(os.path.join(base, path))
        if not candidate.startswith(base + os.sep) and candidate != base:
            return None
        return candidate

    for path, tags_str in rows:
        resolved = _resolve(path)
        if resolved is None or not os.path.exists(resolved):
            continue
        image_paths.append(resolved)
        tags = tags_str.split(',')
        image_labels.append(tags)
        for t in tags:
            unique_tags.add(t)
    
    if not unique_tags:
        return {"success": False, "error": "No valid tags found."}
    
    tag_list = sorted(list(unique_tags))
    label_to_idx = {tag: i for i, tag in enumerate(tag_list)}
    
    # 2. Prepare Model
    model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    # Freeze early layers
    for param in model.parameters():
        param.requires_grad = False
    
    # Replace head
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, len(tag_list))
    
    # 3. Training setup
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    dataset = PhotoDataset(image_paths, image_labels, label_to_idx, transform=transform)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.fc.parameters(), lr=lr)
    
    model.train()
    for epoch in range(epochs):
        for inputs, targets in dataloader:
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
    # 4. Save results
    os.makedirs(os.path.dirname(CUSTOM_MODEL_PATH), exist_ok=True)
    torch.save(model.state_dict(), CUSTOM_MODEL_PATH)
    with open(LABEL_MAP_PATH, 'w') as f:
        json.dump(tag_list, f)
        
    return {"success": True, "tags_trained": len(tag_list), "images_used": len(image_paths)}

if __name__ == "__main__":
    # Expected argv: action db_path photo_base_dir is_admin user_tag models_dir
    action = sys.argv[1] if len(sys.argv) > 1 else 'train'
    DB_PATH = sys.argv[2] if len(sys.argv) > 2 else DB_PATH
    PHOTO_BASE_DIR = sys.argv[3] if len(sys.argv) > 3 else PHOTO_BASE_DIR
    is_admin = (sys.argv[4] if len(sys.argv) > 4 else '').lower() == 'true'
    models_dir = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != 'null' else None
    MODEL_DIR = models_dir or MODEL_DIR or PHOTO_BASE_DIR

    if not DB_PATH or not PHOTO_BASE_DIR:
        print(json.dumps({"success": False, "error": "db_path and photo_base_dir are required"}))
        sys.exit(1)

    CUSTOM_MODEL_PATH = os.path.join(MODEL_DIR, 'custom_resnet50.pth')
    LABEL_MAP_PATH = os.path.join(MODEL_DIR, 'custom_labels.json')

    print(json.dumps(train_model()))
