import os
import torch
import torch.nn as nn
import numpy as np
import cv2
from transformers import ViTImageProcessor, ViTModel

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VIT_PATH = os.path.join(_ROOT, "models", "vit_local")
_OUT_PATH = os.path.join(_ROOT, "models", "vit_head.pt")

def make_synthetic_image(is_fire=True):
    img = np.zeros((224, 224, 3), dtype=np.uint8)
    if is_fire:
        # draw red/orange/yellow blobs
        center = (np.random.randint(50, 174), np.random.randint(50, 174))
        cv2.circle(img, center, 40, (255, np.random.randint(50, 150), 0), -1)
    else:
        # draw grey/blue safe blobs
        center = (np.random.randint(50, 174), np.random.randint(50, 174))
        cv2.circle(img, center, 40, (100, 100, 100), -1)
    return img

def main():
    print("Loading ViT for feature extraction...")
    processor = ViTImageProcessor.from_pretrained(_VIT_PATH, local_files_only=True)
    vit = ViTModel.from_pretrained(_VIT_PATH, local_files_only=True)
    vit.eval()

    print("Generating synthetic dataset (N=200)...")
    X, y = [], []
    for _ in range(100):
        img = make_synthetic_image(is_fire=True)
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            emb = vit(**inputs).pooler_output.squeeze().numpy()
        X.append(emb)
        y.append(1.0)
    for _ in range(100):
        img = make_synthetic_image(is_fire=False)
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            emb = vit(**inputs).pooler_output.squeeze().numpy()
        X.append(emb)
        y.append(0.0)
        
    X = np.array(X)
    y = np.array(y, dtype=np.float32).reshape(-1, 1)

    print("Training Logistic Head on ViT embeddings...")
    class ViTHead(nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = nn.Linear(768, 1)
            self.sigmoid = nn.Sigmoid()
        def forward(self, x):
            return self.sigmoid(self.linear(x))

    model = ViTHead()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.BCELoss()
    
    Xt = torch.tensor(X, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.float32)
    
    for epoch in range(50):
        optimizer.zero_grad()
        out = model(Xt)
        loss = criterion(out, yt)
        loss.backward()
        optimizer.step()

    print(f"Final loss: {loss.item():.4f}")
    torch.save(model.state_dict(), _OUT_PATH)
    print(f"Saved true ViT Head to {_OUT_PATH}")

if __name__ == "__main__":
    main()
