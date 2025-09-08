import argparse
import sys
from typing import List

import cv2
import numpy as np
import matplotlib.pyplot as plt


def _prepare_binary_mask(image_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, th_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    def score(mask: np.ndarray) -> float:
        ratio = float(np.mean(mask == 255))
        return abs(ratio - 0.2)

    mask = th_bin if score(th_bin) < score(th_inv) else th_inv

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def _rotate_image_single_channel(img: np.ndarray, angle_deg: float) -> np.ndarray:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(
        img,
        M,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def _projection_score(bin_img: np.ndarray, target: str) -> float:
    if target == "horizontal":
        proj = np.sum(bin_img, axis=1, dtype=np.float64)
    else:
        proj = np.sum(bin_img, axis=0, dtype=np.float64)
    proj = proj - proj.mean()
    return float(np.dot(proj, proj))


def _search_best_angle(mask: np.ndarray, target: str = "horizontal") -> float:
    def sweep(center: float, span: float, step: float):
        best_a, best_s = None, -1.0
        start = center - span
        end = center + span
        a = start
        while a <= end + 1e-9:
            rotated = _rotate_image_single_channel(mask, a)
            s = _projection_score(rotated, target)
            if s > best_s:
                best_s, best_a = s, a
            a += step
        return best_a, best_s

    best_angle, _ = sweep(0.0, 90.0, 5.0)
    best_angle, _ = sweep(best_angle, 8.0, 1.0)
    best_angle, _ = sweep(best_angle, 1.0, 0.2)

    if best_angle > 90:
        best_angle -= 180
    if best_angle < -90:
        best_angle += 180

    for snap in (0.0, 90.0, -90.0):
        if abs(best_angle - snap) < 0.3:
            best_angle = float(snap)
            break
    return float(best_angle)


def _alignment_and_upright_score(rotated_mask: np.ndarray, target: str) -> float:
    # Alignment: prefer strong structure along target axis
    row_proj = np.sum(rotated_mask, axis=1, dtype=np.float64)
    col_proj = np.sum(rotated_mask, axis=0, dtype=np.float64)
    row_proj = row_proj - row_proj.mean()
    col_proj = col_proj - col_proj.mean()
    var_row = float(np.dot(row_proj, row_proj))
    var_col = float(np.dot(col_proj, col_proj))
    if target == "horizontal":
        align_score = var_row - var_col
    else:
        align_score = var_col - var_row

    # Uprightness: prefer more foreground mass in lower half than upper half
    h = rotated_mask.shape[0]
    upper = float(np.sum(rotated_mask[: h // 2] == 255))
    lower = float(np.sum(rotated_mask[h // 2 :] == 255))
    total = upper + lower + 1e-6
    upright_score = (lower - upper) / total  # [-1, 1]

    # Combined score with small weight on uprightness to avoid dominating
    return align_score + 0.05 * upright_score


def _search_best_clockwise(mask: np.ndarray, target: str = "horizontal") -> float:
    # Evaluate around clockwise bases: 0, -90, -180, -270 degrees
    def local_sweep(base: float) -> tuple:
        # Keep total angle <= 0 to ensure clockwise-only
        best_a, best_s = None, -1e30
        # base 0 only allows non-positive deltas; others allow ±10 while keeping total <= 0
        delta_starts = -10.0
        delta_ends = 0.0 if base == 0.0 else 10.0
        step = 1.0
        a = base + delta_starts
        while a <= base + delta_ends + 1e-9:
            if a > 0.0:
                a += step
                continue
            rotated = _rotate_image_single_channel(mask, a)
            s = _alignment_and_upright_score(rotated, target)
            if s > best_s:
                best_s, best_a = s, a
            a += step
        # refine around best
        if best_a is not None:
            fine_start = max(best_a - 1.0, base + delta_starts)
            fine_end = min(best_a + 1.0, base + delta_ends)
            a = fine_start
            while a <= fine_end + 1e-9:
                if a > 0.0:
                    a += 0.2
                    continue
                rotated = _rotate_image_single_channel(mask, a)
                s = _alignment_and_upright_score(rotated, target)
                if s > best_s:
                    best_s, best_a = s, a
                a += 0.2
        return best_a, best_s

    best_angle, best_score = None, -1e30
    for base in (0.0, -90.0, -180.0, -270.0):
        a, s = local_sweep(base)
        if a is not None and s > best_score:
            best_angle, best_score = a, s

    if best_angle is None:
        return 0.0

    # Snap near canonical angles
    for snap in (0.0, -90.0, -180.0, -270.0):
        if abs(best_angle - snap) < 0.3:
            best_angle = float(snap)
            break

    # Normalize to (-360, 0] to be clearly clockwise
    while best_angle > 0.0:
        best_angle -= 360.0
    while best_angle <= -360.0:
        best_angle += 360.0
    return float(best_angle)


def estimate_correction_angle(image_bgr: np.ndarray, target: str = "horizontal") -> float:
    mask = _prepare_binary_mask(image_bgr)
    # Clockwise-only search with anti-90 and anti-180 heuristics
    return _search_best_clockwise(mask, target=target)


def rotate_image(image_bgr: np.ndarray, angle_deg: float) -> np.ndarray:
    h, w = image_bgr.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(
        image_bgr,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _show_preview(image_bgr: np.ndarray, mask: np.ndarray, rotated_bgr: np.ndarray, angle: float) -> None:
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    rotated_rgb = cv2.cvtColor(rotated_bgr, cv2.COLOR_BGR2RGB)

    plt.figure(figsize=(12, 4))
    ax1 = plt.subplot(1, 3, 1)
    ax1.imshow(image_rgb)
    ax1.set_title("Original")
    ax1.axis("off")

    ax2 = plt.subplot(1, 3, 2)
    ax2.imshow(mask, cmap="gray")
    ax2.set_title("Binary mask")
    ax2.axis("off")

    ax3 = plt.subplot(1, 3, 3)
    ax3.imshow(rotated_rgb)
    ax3.set_title(f"Rotated: {angle:.2f}°")
    ax3.axis("off")

    plt.tight_layout()
    plt.show()


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate rotation and preview result.")
    parser.add_argument("image", nargs="?", default="input.png", help="Path to input image")
    parser.add_argument("--target", choices=["horizontal", "vertical"], default="horizontal", help="Alignment target")
    parser.add_argument("--no-save", action="store_true", help="Do not save output.png")
    parser.add_argument("--no-preview", action="store_true", help="Do not show matplotlib preview window")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    img = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to read image: {args.image}")
        return 2

    mask = _prepare_binary_mask(img)
    angle = estimate_correction_angle(img, target=args.target)
    rotated = rotate_image(img, angle)

    if not args.no_save:
        cv2.imwrite("output.png", rotated)

    if not args.no_preview:
        _show_preview(img, mask, rotated, angle)

    print(f"rotate by: {angle:.2f} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

