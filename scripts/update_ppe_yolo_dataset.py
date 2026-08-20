import os
import shutil
import yaml

TARGET_DIR = r"c:\Users\Asus\Downloads\DATASET\ppe_yolo_dataset"
DATASET_BASE_DIR = r"c:\Users\Asus\Downloads\DATASET"

# 18 Target Classes for ppe_yolo_dataset
TARGET_CLASSES = [
    "person",          # 0
    "helmet",          # 1
    "vest",            # 2
    "boots",           # 3
    "lanyard",         # 4
    "no_harness",      # 5
    "no_lanyard",      # 6
    "lanyard_good",    # 7
    "lanyard_bad",     # 8
    "glove",           # 9
    "glass",           # 10
    "ear_protection",  # 11
    "mask",            # 12
    "no_helmet",       # 13
    "no_vest",         # 14
    "no_boots",        # 15
    "no_glove",        # 16
    "no_glass",        # 17
]

TARGET_CLASS_TO_ID = {name: i for i, name in enumerate(TARGET_CLASSES)}

# Mappings for external source datasets to target class IDs
DATASET_MAPPINGS = {
    "construction-ppe": {
        # source_id: target_id
        0: TARGET_CLASS_TO_ID["helmet"],         # helmet -> helmet (1)
        1: TARGET_CLASS_TO_ID["glove"],          # gloves -> glove (9)
        2: TARGET_CLASS_TO_ID["vest"],           # vest -> vest (2)
        3: TARGET_CLASS_TO_ID["boots"],          # boots -> boots (3)
        4: TARGET_CLASS_TO_ID["glass"],          # goggles -> glass (10)
        # 5: none -> skip
        6: TARGET_CLASS_TO_ID["person"],         # Person -> person (0)
        7: TARGET_CLASS_TO_ID["no_helmet"],      # no_helmet -> no_helmet (13)
        8: TARGET_CLASS_TO_ID["no_glass"],       # no_goggle -> no_glass (17)
        9: TARGET_CLASS_TO_ID["no_glove"],       # no_gloves -> no_glove (16)
        10: TARGET_CLASS_TO_ID["no_boots"],      # no_boots -> no_boots (15)
    },
    "archive": {
        0: TARGET_CLASS_TO_ID["ear_protection"], # ear -> ear_protection (11)
        1: TARGET_CLASS_TO_ID["ear_protection"], # ear-mufs -> ear_protection (11)
        3: TARGET_CLASS_TO_ID["mask"],           # face-guard -> mask (12)
        4: TARGET_CLASS_TO_ID["mask"],           # face-mask -> mask (12)
        5: TARGET_CLASS_TO_ID["boots"],          # foot -> boots (3)
        6: TARGET_CLASS_TO_ID["glass"],          # glasses -> glass (10)
        7: TARGET_CLASS_TO_ID["glove"],          # gloves -> glove (9)
        10: TARGET_CLASS_TO_ID["helmet"],        # helmet -> helmet (1)
        12: TARGET_CLASS_TO_ID["person"],        # person -> person (0)
        13: TARGET_CLASS_TO_ID["vest"],          # safety-suit -> vest (2)
        14: TARGET_CLASS_TO_ID["vest"],          # safety-vest -> vest (2)
        15: TARGET_CLASS_TO_ID["boots"],          # shoes -> boots (3)
    },
    "construction safety.v2-release.yolov11": {
        0: TARGET_CLASS_TO_ID["helmet"],         # helmet -> helmet (1)
        1: TARGET_CLASS_TO_ID["no_helmet"],      # no-helmet -> no_helmet (13)
        2: TARGET_CLASS_TO_ID["no_vest"],        # no-vest -> no_vest (14)
        3: TARGET_CLASS_TO_ID["person"],         # person -> person (0)
        4: TARGET_CLASS_TO_ID["vest"],           # vest -> vest (2)
    },
    "Hard Hat Sample.v2-augmented-416x416.yolov11": {
        1: TARGET_CLASS_TO_ID["helmet"],         # helmet -> helmet (1)
        2: TARGET_CLASS_TO_ID["person"],         # person -> person (0)
    },
    "harness and lanyard detection.v1i.yolov11": {
        0: TARGET_CLASS_TO_ID["lanyard_bad"],    # lanyard_bad -> lanyard_bad (8)
        1: TARGET_CLASS_TO_ID["lanyard_good"],   # lanyard_good -> lanyard_good (7)
        2: TARGET_CLASS_TO_ID["no_harness"],     # no_harness -> no_harness (5)
        3: TARGET_CLASS_TO_ID["no_lanyard"],     # no_lanyard -> no_lanyard (6)
    }
}

def process_dataset(src_name, mapping):
    src_dir = os.path.join(DATASET_BASE_DIR, src_name)
    if not os.path.exists(src_dir):
        print(f"Skipping missing source dataset: {src_name}")
        return

    prefix = src_name.split(".")[0].replace(" ", "_").lower()
    print(f"\nMerging '{src_name}' (prefix: {prefix})...")

    copied_images = 0
    copied_labels = 0

    for split in ["train", "val", "test"]:
        # Find images folder in source
        possible_img_dirs = [
            os.path.join(src_dir, split, "images"),
            os.path.join(src_dir, "images", split),
            os.path.join(src_dir, split),
        ]
        if split == "val":
            possible_img_dirs.extend([
                os.path.join(src_dir, "valid", "images"),
                os.path.join(src_dir, "images", "valid"),
                os.path.join(src_dir, "valid"),
            ])

        src_img_dir = None
        for d in possible_img_dirs:
            if os.path.exists(d) and os.path.isdir(d):
                files = os.listdir(d)
                if any(f.lower().endswith(('.jpg', '.jpeg', '.png')) for f in files):
                    src_img_dir = d
                    break

        if not src_img_dir:
            continue

        # Find labels folder in source
        possible_lbl_dirs = [
            os.path.join(os.path.dirname(src_img_dir), "labels"),
            src_img_dir.replace("images", "labels")
        ]
        src_lbl_dir = None
        for d in possible_lbl_dirs:
            if os.path.exists(d) and os.path.isdir(d):
                src_lbl_dir = d
                break

        if not src_lbl_dir:
            continue

        # Target directories
        tgt_img_dir = os.path.join(TARGET_DIR, split, "images")
        tgt_lbl_dir = os.path.join(TARGET_DIR, split, "labels")
        os.makedirs(tgt_img_dir, exist_ok=True)
        os.makedirs(tgt_lbl_dir, exist_ok=True)

        for img_file in os.listdir(src_img_dir):
            ext = os.path.splitext(img_file)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png']:
                continue

            base_name = os.path.splitext(img_file)[0]
            lbl_file = base_name + ".txt"
            src_lbl_path = os.path.join(src_lbl_dir, lbl_file)

            if not os.path.exists(src_lbl_path):
                continue

            # Read and remap label file
            remapped_lines = []
            with open(src_lbl_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if not parts:
                        continue
                    src_cls = int(parts[0])
                    if src_cls in mapping:
                        tgt_cls = mapping[src_cls]
                        remapped_lines.append(f"{tgt_cls} {' '.join(parts[1:])}\n")

            if not remapped_lines:
                continue

            # Generate unique filename with dataset prefix
            new_base = f"{prefix}_{base_name}"
            new_img_file = f"{new_base}{ext}"
            new_lbl_file = f"{new_base}.txt"

            tgt_img_path = os.path.join(tgt_img_dir, new_img_file)
            tgt_lbl_path = os.path.join(tgt_lbl_dir, new_lbl_file)

            shutil.copy2(os.path.join(src_img_dir, img_file), tgt_img_path)
            with open(tgt_lbl_path, "w", encoding="utf-8") as f:
                f.writelines(remapped_lines)

            copied_images += 1
            copied_labels += 1

    print(f"Finished '{src_name}': Copied {copied_images} images and remapped {copied_labels} label files.")

def update_yaml_configs():
    print("\nUpdating data.yaml files...")
    data_yaml_content = {
        "path": TARGET_DIR.replace("\\", "/"),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "nc": len(TARGET_CLASSES),
        "names": {i: name for i, name in enumerate(TARGET_CLASSES)}
    }

    # Update TARGET_DIR/data.yaml
    tgt_yaml_path = os.path.join(TARGET_DIR, "data.yaml")
    with open(tgt_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_yaml_content, f, sort_keys=False)
    print(f"Updated {tgt_yaml_path}")

    # Update project root data.yaml
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proj_data_yaml = os.path.join(project_root, "data.yaml")
    with open(proj_data_yaml, "w", encoding="utf-8") as f:
        yaml.dump(data_yaml_content, f, sort_keys=False)
    print(f"Updated {proj_data_yaml}")

    # Update project dataset.yaml
    proj_dataset_yaml = os.path.join(project_root, "dataset.yaml")
    dataset_yaml_content = {
        "path": TARGET_DIR.replace("\\", "/"),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "nc": len(TARGET_CLASSES),
        "names": {i: name for i, name in enumerate(TARGET_CLASSES)}
    }
    with open(proj_dataset_yaml, "w", encoding="utf-8") as f:
        yaml.dump(dataset_yaml_content, f, sort_keys=False)
    print(f"Updated {proj_dataset_yaml}")

def verify_dataset_stats():
    print("\n" + "="*50)
    print("DATASET VERIFICATION STATS")
    print("="*50)
    counts = {i: 0 for i in range(len(TARGET_CLASSES))}
    total_images = 0

    for split in ["train", "val", "test"]:
        lbl_dir = os.path.join(TARGET_DIR, split, "labels")
        if not os.path.exists(lbl_dir):
            continue
        for lbl_file in os.listdir(lbl_dir):
            if not lbl_file.endswith(".txt"):
                continue
            total_images += 1
            with open(os.path.join(lbl_dir, lbl_file), "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        cls_id = int(parts[0])
                        if cls_id in counts:
                            counts[cls_id] += 1

    print(f"Total Label Files in ppe_yolo_dataset: {total_images}")
    print("\nPer-class Bounding Box Counts:")
    for cls_id, name in enumerate(TARGET_CLASSES):
        print(f"  [{cls_id:2d}] {name:<16}: {counts[cls_id]:6d} boxes")
    print("="*50)

if __name__ == "__main__":
    for src_name, mapping in DATASET_MAPPINGS.items():
        process_dataset(src_name, mapping)
    update_yaml_configs()
    verify_dataset_stats()
