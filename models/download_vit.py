import os
from transformers import ViTImageProcessor, ViTForImageClassification

def main():
    print("Downloading ViT...")
    processor = ViTImageProcessor.from_pretrained('google/vit-base-patch16-224')
    model = ViTForImageClassification.from_pretrained('google/vit-base-patch16-224')
    out_dir = os.path.join(os.path.dirname(__file__), 'vit_local')
    processor.save_pretrained(out_dir)
    model.save_pretrained(out_dir)
    print(f"ViT saved to {out_dir}")

if __name__ == "__main__":
    main()
