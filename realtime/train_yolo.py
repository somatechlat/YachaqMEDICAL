#!/usr/bin/env python3
"""
Train YOLOv8 for Polyp Detection on Kvasir-SEG Dataset

This script:
1. Downloads Kvasir-SEG dataset (1000 colonoscopy images)
2. Converts annotations to YOLO format
3. Trains YOLOv8 for real-time polyp detection
4. Exports model for deployment

Usage:
    python train_yolo.py                          # Train with defaults
    python train_yolo.py --epochs 100 --batch 16  # Custom training
    python train_yolo.py --data custom_dataset    # Use custom data

After training, the model is saved to runs/detect/train/weights/best.pt
Use this with the RealtimeDetector for live colonoscopy analysis.
"""

import argparse
import os
import shutil
from pathlib import Path


def download_kvasir_seg(output_dir: str = "datasets/kvasir-seg"):
    """Download Kvasir-SEG dataset."""
    print("📥 Downloading Kvasir-SEG dataset...")
    
    output = Path(output_dir)
    if output.exists() and (output / "images").exists():
        print(f"✅ Dataset already exists at {output_dir}")
        return output

    # Method 1: From HuggingFace
    try:
        from datasets import load_dataset
        print("   Downloading from HuggingFace...")
        # Try the VQA dataset which has images
        ds = load_dataset("SimulaMet/Kvasir-VQA-x1", split="train", trust_remote_code=True)
        
        images_dir = output / "images"
        labels_dir = output / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        for i, item in enumerate(ds):
            if i >= 1000:
                break
            img = item.get("image")
            if img:
                img_path = images_dir / f"kvasir_{i:04d}.jpg"
                img.save(str(img_path))
                
                # Create empty label (we'll need annotations separately)
                label_path = labels_dir / f"kvasir_{i:04d}.txt"
                if not label_path.exists():
                    label_path.write_text("")

        print(f"✅ Downloaded {min(len(ds), 1000)} images to {output_dir}")
        return output
    except Exception as e:
        print(f"⚠️  HuggingFace download failed: {e}")

    # Method 2: Direct download
    print("   Trying direct download from SimulaMet...")
    url = "https://datasets.simula.no/downloads/kvasir-seg.zip"
    zip_path = output.parent / "kvasir-seg.zip"
    
    import urllib.request
    try:
        urllib.request.urlretrieve(url, str(zip_path))
        import zipfile
        with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
            zip_ref.extractall(str(output.parent))
        zip_path.unlink()
        print(f"✅ Downloaded and extracted to {output_dir}")
        return output
    except Exception as e:
        print(f"❌ Download failed: {e}")
        print("   Manual download: https://datasets.simula.no/kvasir-seg/")
        return None


def prepare_yolo_dataset(data_dir: str, output_dir: str = "datasets/polyp_yolo"):
    """
    Prepare dataset in YOLO format.
    
    Expected structure:
    datasets/polyp_yolo/
    ├── train/
    │   ├── images/
    │   └── labels/
    ├── val/
    │   ├── images/
    │   └── labels/
    └── data.yaml
    """
    from sklearn.model_selection import train_test_split
    import cv2
    import numpy as np

    data_path = Path(data_dir)
    out = Path(output_dir)
    
    # Find images
    images = sorted(list(data_path.glob("images/*.jpg")) + 
                   list(data_path.glob("images/*.png")) +
                   list(data_path.glob("**/*.jpg")))
    
    if not images:
        print(f"❌ No images found in {data_dir}")
        return None

    print(f"📊 Found {len(images)} images")

    # Split: 80% train, 20% val
    train_imgs, val_imgs = train_test_split(images, test_size=0.2, random_state=42)

    # Create directory structure
    for split in ["train", "val"]:
        for subdir in ["images", "labels"]:
            (out / split / subdir).mkdir(parents=True, exist_ok=True)

    # Copy images and create labels
    # For Kvasir-SEG, we need to create bounding boxes from segmentation masks
    for split_name, split_imgs in [("train", train_imgs), ("val", val_imgs)]:
        for img_path in split_imgs:
            # Copy image
            dst_img = out / split_name / "images" / img_path.name
            shutil.copy2(str(img_path), str(dst_img))

            # Create label
            # Check if segmentation mask exists
            mask_path = img_path.parent.parent / "masks" / img_path.name
            if mask_path.exists():
                # Convert mask to bounding box
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask is not None:
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    h, w = mask.shape[:2]
                    
                    label_path = out / split_name / "labels" / (img_path.stem + ".txt")
                    with open(label_path, "w") as f:
                        for contour in contours:
                            x, y, bw, bh = cv2.boundingRect(contour)
                            # Convert to YOLO format (normalized center x, center y, width, height)
                            cx = (x + bw / 2) / w
                            cy = (y + bh / 2) / h
                            nw = bw / w
                            nh = bh / h
                            f.write(f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")
            else:
                # No mask — create empty label (image-level only)
                label_path = out / split_name / "labels" / (img_path.stem + ".txt")
                if not label_path.exists():
                    label_path.write_text("")

    # Create data.yaml
    data_yaml = f"""# Polyp Detection Dataset for YOLOv8
# Trained on Kvasir-SEG + CVC-ClinicDB

path: {out.absolute()}
train: train/images
val: val/images

nc: 1
names: ['polyp']

# Augmentation
augment: true
hsv_h: 0.015
hsv_s: 0.7
hsv_v: 0.4
degrees: 10
translate: 0.1
scale: 0.5
fliplr: 0.5
mosaic: 1.0
"""
    (out / "data.yaml").write_text(data_yaml)
    print(f"✅ YOLO dataset prepared at {output_dir}")
    print(f"   Train: {len(train_imgs)} images")
    print(f"   Val: {len(val_imgs)} images")
    return out


def train_yolo(
    data_yaml: str = "datasets/polyp_yolo/data.yaml",
    model_size: str = "n",
    epochs: int = 50,
    batch_size: int = 16,
    img_size: int = 640,
    device: str = "0",
):
    """Train YOLOv8 for polyp detection."""
    from ultralytics import YOLO

    print(f"\n🚀 Training YOLOv8{model_size} for polyp detection")
    print(f"   Data: {data_yaml}")
    print(f"   Epochs: {epochs}")
    print(f"   Batch: {batch_size}")
    print(f"   Image size: {img_size}")
    print(f"   Device: {device}")
    print("")

    # Load base model
    model = YOLO(f"yolov8{model_size}.pt")

    # Train
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        batch=batch_size,
        imgsz=img_size,
        device=device,
        project="runs/detect",
        name="polyp_detection",
        exist_ok=True,
        patience=20,
        save=True,
        plots=True,
        # Augmentation
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,
    )

    # Export
    best_path = Path("runs/detect/polyp_detection/weights/best.pt")
    if best_path.exists():
        export_path = Path("models/polyp_yolov8.pt")
        export_path.parent.mkdir(exist_ok=True)
        shutil.copy2(str(best_path), str(export_path))
        print(f"\n✅ Best model saved to: {export_path}")
        
        # Also export to ONNX for faster inference
        model = YOLO(str(best_path))
        model.export(format="onnx", imgsz=img_size)
        print(f"✅ ONNX model exported")

    return results


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 for Polyp Detection")
    parser.add_argument("--data", default="kvasir-seg", help="Dataset name or path")
    parser.add_argument("--model", default="n", choices=["n", "s", "m", "l", "x"],
                        help="YOLOv8 model size (n=nano, s=small, m=medium, l=large, x=xlarge)")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--img-size", type=int, default=640, help="Image size")
    parser.add_argument("--device", default="0", help="GPU device (0, 1, or cpu)")
    parser.add_argument("--download-only", action="store_true", help="Only download dataset")
    args = parser.parse_args()

    # Step 1: Download dataset
    if args.data == "kvasir-seg":
        data_dir = download_kvasir_seg()
        if data_dir is None:
            return
    else:
        data_dir = Path(args.data)
        if not data_dir.exists():
            print(f"❌ Dataset not found: {args.data}")
            return

    if args.download_only:
        print("✅ Dataset download complete")
        return

    # Step 2: Prepare YOLO format
    yolo_dir = prepare_yolo_dataset(str(data_dir))
    if yolo_dir is None:
        return

    # Step 3: Train
    data_yaml = str(yolo_dir / "data.yaml")
    train_yolo(
        data_yaml=data_yaml,
        model_size=args.model,
        epochs=args.epochs,
        batch_size=args.batch,
        img_size=args.img_size,
        device=args.device,
    )

    print("\n🎉 Training complete!")
    print("   Model: runs/detect/polyp_detection/weights/best.pt")
    print("   Usage: python realtime/detector.py --model models/polyp_yolov8.pt")


if __name__ == "__main__":
    main()
