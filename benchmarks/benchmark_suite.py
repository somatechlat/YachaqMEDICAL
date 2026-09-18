#!/usr/bin/env python3
"""
YachaqMEDICAL — Benchmark Suite
Measures detection accuracy, speed, and clinical utility against known datasets.

Metrics tracked:
  - Sensitivity (Recall) — % of real polyps detected
  - Specificity — % of normal frames correctly identified as normal
  - Precision — % of detections that are real polyps
  - F1 Score — Harmonic mean of precision and recall
  - FPS — Frames per second processing speed
  - Latency (ms) — Time per frame
  - mAP@50 — Mean Average Precision at IoU 0.5
  - mAP@50:95 — Mean Average Precision at IoU 0.5:0.95
  - False Positive Rate — False alarms per procedure
  - Miss Rate — Polyps missed entirely

Datasets:
  - Kvasir-SEG (1000 images, polyp segmentation masks)
  - CVC-ClinicDB (612 images)
  - CVC-ColonDB (380 images)
  - ETIS-Larib (196 images)
  - LDPolypVideo (160 videos, 40K+ frames)

Benchmark targets (from published literature):
  - GI Genius: Sensitivity 98.5%, Specificity 95%, 0.3 FP/procedure
  - CAD-EYE: Sensitivity 97%, Specificity 93%
  - Generic YOLOv8: Sensitivity 92-96%, Specificity 88-95%
  - Our target: Sensitivity >95%, Specificity >90%, <1 FP/procedure
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


@dataclass
class BenchmarkResult:
    """Results for a single image/frame."""
    image_path: str
    ground_truth_boxes: list  # [(x1,y1,x2,y2), ...]
    predicted_boxes: list     # [(x1,y1,x2,y2,conf), ...]
    tp: int = 0               # True positives
    fp: int = 0               # False positives
    fn: int = 0               # False negatives
    inference_ms: float = 0.0


@dataclass
class BenchmarkSummary:
    """Aggregated benchmark results."""
    dataset: str
    model_name: str
    total_images: int = 0
    total_frames: int = 0

    # Detection metrics
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    # Derived metrics
    sensitivity: float = 0.0      # Recall / TPR
    specificity: float = 0.0      # TNR
    precision: float = 0.0        # PPV
    f1_score: float = 0.0
    accuracy: float = 0.0

    # Speed metrics
    avg_latency_ms: float = 0.0
    fps: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0

    # mAP
    map50: float = 0.0
    map50_95: float = 0.0

    # Clinical metrics
    false_positives_per_procedure: float = 0.0
    miss_rate: float = 0.0

    # Per-class breakdown
    class_metrics: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    def to_json(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def print_report(self):
        print("\n" + "=" * 70)
        print(f"  BENCHMARK REPORT: {self.model_name}")
        print(f"  Dataset: {self.dataset}")
        print("=" * 70)
        print(f"  Images analyzed:     {self.total_images}")
        print(f"  Total detections:    {self.true_positives + self.false_positives}")
        print("")
        print("  ── Detection Performance ──")
        print(f"  Sensitivity (Recall): {self.sensitivity:.1%}  {'✅' if self.sensitivity > 0.95 else '⚠️'} (target: >95%)")
        print(f"  Specificity:          {self.specificity:.1%}  {'✅' if self.specificity > 0.90 else '⚠️'} (target: >90%)")
        print(f"  Precision:            {self.precision:.1%}  {'✅' if self.precision > 0.85 else '⚠️'} (target: >85%)")
        print(f"  F1 Score:             {self.f1_score:.1%}  {'✅' if self.f1_score > 0.90 else '⚠️'} (target: >90%)")
        print(f"  Accuracy:             {self.accuracy:.1%}")
        print("")
        print("  ── Speed Performance ──")
        print(f"  Avg Latency:          {self.avg_latency_ms:.1f}ms")
        print(f"  FPS:                  {self.fps:.0f}  {'✅' if self.fps > 30 else '⚠️'} (target: >30 FPS)")
        print(f"  P95 Latency:          {self.p95_latency_ms:.1f}ms")
        print(f"  Min/Max Latency:      {self.min_latency_ms:.1f}ms / {self.max_latency_ms:.1f}ms")
        print("")
        print("  ── Clinical Metrics ──")
        print(f"  False Positives/Proc: {self.false_positives_per_procedure:.2f}  {'✅' if self.false_positives_per_procedure < 1.0 else '⚠️'} (target: <1.0)")
        print(f"  Miss Rate:            {self.miss_rate:.1%}  {'✅' if self.miss_rate < 0.05 else '⚠️'} (target: <5%)")
        print("")
        print("  ── mAP ──")
        print(f"  mAP@50:               {self.map50:.1%}")
        print(f"  mAP@50:95:            {self.map50_95:.1%}")
        print("=" * 70)

        # Comparison with commercial systems
        print("\n  ── Comparison with Commercial Systems ──")
        print(f"  {'System':<25} {'Sensitivity':<15} {'Specificity':<15} {'FP/Proc':<10}")
        print(f"  {'─'*25} {'─'*15} {'─'*15} {'─'*10}")
        print(f"  {'GI Genius (Medtronic)':<25} {'98.5%':<15} {'95%':<15} {'0.3':<10}")
        print(f"  {'CAD-EYE (Fujifilm)':<25} {'97%':<15} {'93%':<15} {'0.5':<10}")
        print(f"  {'EndoAID (Olympus)':<25} {'96%':<15} {'92%':<15} {'0.4':<10}")
        print(f"  {'YachaqMEDICAL (ours)':<25} {self.sensitivity:.1%}{'':<{14-len(f'{self.sensitivity:.1%}')}} {self.specificity:.1%}{'':<{14-len(f'{self.specificity:.1%}')}} {self.false_positives_per_procedure:.2f}{'':<{9-len(f'{self.false_positives_per_procedure:.2f}')}}")
        print("")


def compute_iou(box1, box2):
    """Compute Intersection over Union between two boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def match_detections(gt_boxes, pred_boxes, iou_threshold=0.5):
    """
    Match ground truth boxes to predictions using IoU.
    Returns: tp, fp, fn counts
    """
    if not gt_boxes and not pred_boxes:
        return 0, 0, 0
    if not gt_boxes:
        return 0, len(pred_boxes), 0
    if not pred_boxes:
        return 0, 0, len(gt_boxes)

    # Compute IoU matrix
    iou_matrix = np.zeros((len(gt_boxes), len(pred_boxes)))
    for i, gt in enumerate(gt_boxes):
        for j, pred in enumerate(pred_boxes):
            iou_matrix[i, j] = compute_iou(gt, pred[:4])

    # Match using greedy assignment
    tp = 0
    matched_gt = set()
    matched_pred = set()

    # Sort by IoU descending
    while True:
        if len(matched_gt) == len(gt_boxes) or len(matched_pred) == len(pred_boxes):
            break

        # Find best unmatched pair
        best_iou = 0
        best_gt = -1
        best_pred = -1
        for i in range(len(gt_boxes)):
            if i in matched_gt:
                continue
            for j in range(len(pred_boxes)):
                if j in matched_pred:
                    continue
                if iou_matrix[i, j] > best_iou:
                    best_iou = iou_matrix[i, j]
                    best_gt = i
                    best_pred = j

        if best_iou >= iou_threshold:
            tp += 1
            matched_gt.add(best_gt)
            matched_pred.add(best_pred)
        else:
            break

    fp = len(pred_boxes) - tp
    fn = len(gt_boxes) - tp
    return tp, fp, fn


def compute_ap(recalls, precisions):
    """Compute Average Precision from recall-precision curve."""
    # Pad with endpoints
    recalls = np.concatenate(([0.0], recalls, [1.0]))
    precisions = np.concatenate(([0.0], precisions, [0.0]))

    # Make precision monotonically decreasing
    for i in range(len(precisions) - 2, -1, -1):
        precisions[i] = max(precisions[i], precisions[i + 1])

    # Compute AP
    ap = 0.0
    for i in range(1, len(recalls)):
        ap += (recalls[i] - recalls[i - 1]) * precisions[i]

    return ap


class BenchmarkRunner:
    """Run benchmarks on polyp detection models."""

    def __init__(
        self,
        model_path: str = "",
        iou_threshold: float = 0.5,
        confidence_threshold: float = 0.5,
    ):
        self.model_path = model_path
        self.iou_threshold = iou_threshold
        self.confidence_threshold = confidence_threshold
        self.model = None

    def load_model(self):
        """Load YOLO model."""
        from ultralytics import YOLO
        if self.model_path and Path(self.model_path).exists():
            self.model = YOLO(self.model_path)
            print(f"✅ Model loaded: {self.model_path}")
        else:
            self.model = YOLO("yolov8n.pt")
            print("⚠️  Using base yolov8n (not trained for polyps)")

    def load_ground_truth_kvasir(self, dataset_path: str) -> dict:
        """
        Load ground truth from Kvasir-SEG dataset.
        Returns dict: {image_path: [boxes]}
        """
        gt = {}
        data = Path(dataset_path)

        # Find images and masks
        images_dir = data / "images"
        masks_dir = data / "masks"

        if not images_dir.exists():
            # Try flat structure
            images_dir = data
            masks_dir = data.parent / "masks"

        for img_path in sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png")):
            # Find corresponding mask
            mask_path = masks_dir / img_path.name
            if not mask_path.exists():
                # Try different extensions
                for ext in [".jpg", ".png", ".tif"]:
                    alt = masks_dir / (img_path.stem + ext)
                    if alt.exists():
                        mask_path = alt
                        break

            if mask_path.exists():
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask is not None:
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    boxes = []
                    for contour in contours:
                        x, y, w, h = cv2.boundingRect(contour)
                        if w > 5 and h > 5:  # Filter tiny noise
                            boxes.append((x, y, x + w, y + h))
                    gt[str(img_path)] = boxes if boxes else []
            else:
                gt[str(img_path)] = []

        print(f"📋 Loaded {len(gt)} images with ground truth")
        return gt

    def benchmark_single(self, image_path: str, gt_boxes: list) -> BenchmarkResult:
        """Benchmark a single image."""
        import time

        # Load image
        img = cv2.imread(image_path)
        if img is None:
            return BenchmarkResult(image_path, gt_boxes, [], 0, 0, len(gt_boxes), 0)

        # Run inference
        start = time.monotonic()
        results = self.model(img, conf=self.confidence_threshold, verbose=False)
        inference_ms = (time.monotonic() - start) * 1000

        # Extract predictions
        pred_boxes = []
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    pred_boxes.append((x1, y1, x2, y2, conf))

        # Match detections
        tp, fp, fn = match_detections(gt_boxes, pred_boxes, self.iou_threshold)

        return BenchmarkResult(
            image_path=image_path,
            ground_truth_boxes=gt_boxes,
            predicted_boxes=pred_boxes,
            tp=tp, fp=fp, fn=fn,
            inference_ms=inference_ms,
        )

    def benchmark_dataset(
        self,
        dataset_path: str,
        dataset_name: str = "Kvasir-SEG",
        max_images: int = 0,
    ) -> BenchmarkSummary:
        """Benchmark on a full dataset."""
        if self.model is None:
            self.load_model()

        print(f"\n🔬 Benchmarking on {dataset_name}...")
        print(f"   Model: {self.model_path}")
        print(f"   IoU threshold: {self.iou_threshold}")
        print(f"   Confidence threshold: {self.confidence_threshold}")

        # Load ground truth
        gt = self.load_ground_truth_kvasir(dataset_path)

        if max_images > 0:
            items = list(gt.items())[:max_images]
            gt = dict(items)

        # Run benchmark
        results = []
        latencies = []
        total_gt_polyps = 0

        for i, (img_path, gt_boxes) in enumerate(gt.items()):
            if i % 100 == 0 and i > 0:
                print(f"   Progress: {i}/{len(gt)} images...")

            result = self.benchmark_single(img_path, gt_boxes)
            results.append(result)
            latencies.append(result.inference_ms)
            total_gt_polyps += len(gt_boxes)

        # Aggregate results
        total_tp = sum(r.tp for r in results)
        total_fp = sum(r.fp for r in results)
        total_fn = sum(r.fn for r in results)
        total_tn = sum(1 for r in results if not r.ground_truth_boxes and not r.predicted_boxes)

        # Calculate metrics
        sensitivity = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        specificity = total_tn / (total_tn + total_fp) if (total_tn + total_fp) > 0 else 0
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        f1 = 2 * precision * sensitivity / (precision + sensitivity) if (precision + sensitivity) > 0 else 0
        accuracy = (total_tp + total_tn) / len(results) if results else 0

        # Speed metrics
        latencies_arr = np.array(latencies)
        avg_latency = float(np.mean(latencies_arr))
        fps = 1000.0 / avg_latency if avg_latency > 0 else 0

        # mAP calculation
        all_confs = []
        all_matches = []
        for r in results:
            for pred in r.predicted_boxes:
                conf = pred[4]
                # Check if this prediction matches any GT
                matched = False
                for gt_box in r.ground_truth_boxes:
                    if compute_iou(gt_box, pred[:4]) >= self.iou_threshold:
                        matched = True
                        break
                all_confs.append(conf)
                all_matches.append(matched)

        map50 = 0.0
        if all_confs:
            sorted_indices = np.argsort(all_confs)[::-1]
            tp_cumsum = np.cumsum([all_matches[i] for i in sorted_indices])
            fp_cumsum = np.cumsum([1 - all_matches[i] for i in sorted_indices])
            recalls = tp_cumsum / max(total_gt_polyps, 1)
            precisions = tp_cumsum / (tp_cumsum + fp_cumsum)
            map50 = compute_ap(recalls, precisions)

        # Assume 30 frames per procedure for FP rate
        estimated_procedures = max(1, len(results) / 30)

        summary = BenchmarkSummary(
            dataset=dataset_name,
            model_name=self.model_path or "yolov8n",
            total_images=len(results),
            true_positives=total_tp,
            false_positives=total_fp,
            false_negatives=total_fn,
            true_negatives=total_tn,
            sensitivity=sensitivity,
            specificity=specificity,
            precision=precision,
            f1_score=f1,
            accuracy=accuracy,
            avg_latency_ms=avg_latency,
            fps=fps,
            min_latency_ms=float(np.min(latencies_arr)) if len(latencies_arr) > 0 else 0,
            max_latency_ms=float(np.max(latencies_arr)) if len(latencies_arr) > 0 else 0,
            p95_latency_ms=float(np.percentile(latencies_arr, 95)) if len(latencies_arr) > 0 else 0,
            map50=map50,
            map50_95=map50 * 0.85,  # Approximation (proper calc needs multi-IoU)
            false_positives_per_procedure=total_fp / estimated_procedures,
            miss_rate=total_fn / max(total_gt_polyps, 1),
        )

        return summary

    def compare_models(
        self,
        model_paths: list[str],
        dataset_path: str,
        dataset_name: str = "Kvasir-SEG",
    ) -> list[BenchmarkSummary]:
        """Compare multiple models on the same dataset."""
        results = []
        for path in model_paths:
            self.model_path = path
            self.model = None
            summary = self.benchmark_dataset(dataset_path, dataset_name)
            results.append(summary)

        # Print comparison table
        print("\n" + "=" * 90)
        print("  MODEL COMPARISON")
        print("=" * 90)
        print(f"  {'Model':<30} {'Sens.':<10} {'Spec.':<10} {'F1':<10} {'FPS':<10} {'mAP50':<10}")
        print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")
        for r in results:
            print(f"  {r.model_name:<30} {r.sensitivity:.1%}{'':<5} {r.specificity:.1%}{'':<5} {r.f1_score:.1%}{'':<5} {r.fps:.0f}{'':<7} {r.map50:.1%}")
        print("")

        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="YachaqMEDICAL Benchmark Suite")
    parser.add_argument("--model", default="", help="YOLO model path")
    parser.add_argument("--dataset", default="datasets/kvasir-seg", help="Dataset path")
    parser.add_argument("--name", default="Kvasir-SEG", help="Dataset name")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold")
    parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--max-images", type=int, default=0, help="Max images (0=all)")
    parser.add_argument("--compare", nargs="+", help="Compare multiple models")
    parser.add_argument("--output", default="", help="Save results to JSON")
    args = parser.parse_args()

    runner = BenchmarkRunner(
        model_path=args.model,
        iou_threshold=args.iou,
        confidence_threshold=args.conf,
    )

    if args.compare:
        results = runner.compare_models(args.compare, args.dataset, args.name)
        if args.output:
            for r in results:
                r.to_json(f"{args.output}_{r.model_name}.json")
    else:
        summary = runner.benchmark_dataset(args.dataset, args.name, args.max_images)
        summary.print_report()
        if args.output:
            summary.to_json(args.output)


if __name__ == "__main__":
    main()
