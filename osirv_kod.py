import numpy as np
import cv2
import random
import matplotlib.pyplot as plt
from scipy.ndimage import distance_transform_edt, gaussian_filter

SEED = 24


# ============================================================================
# POZADINA -- "watercolor" stil (domain warping + fraktalni sum + grain)
# ============================================================================

def _fractal_noise(width, height, rng, octaves=5, base_res=4, persistence=0.55, lacunarity=2.2):
    result = np.zeros((height, width), dtype=np.float32)
    amplitude = 1.0
    total_amplitude = 0.0
    res = base_res

    for _ in range(octaves):
        noise = rng.randn(res, res).astype(np.float32)
        upsampled = cv2.resize(noise, (width, height), interpolation=cv2.INTER_CUBIC)
        result += upsampled * amplitude
        total_amplitude += amplitude
        amplitude *= persistence
        res = max(2, int(res * lacunarity))

    return result / total_amplitude


def _domain_warp(width, height, rng, strength=35, scale=6):
    dx = rng.randn(scale, scale).astype(np.float32)
    dy = rng.randn(scale, scale).astype(np.float32)
    dx = cv2.resize(dx, (width, height), interpolation=cv2.INTER_CUBIC)
    dy = cv2.resize(dy, (width, height), interpolation=cv2.INTER_CUBIC)
    dx = gaussian_filter(dx, sigma=25) * strength
    dy = gaussian_filter(dy, sigma=25) * strength
    return dx, dy


def generate_angiogram_background(
    width=768,
    height=768,
    seed=SEED,
    base_tone=0.42,
    blotch_strength=0.16,
    warp_strength=40,
    grain_strength=0.018,
    contrast=1.0,
):
    
    rng = np.random.RandomState(seed)

    dx, dy = _domain_warp(width, height, rng, strength=warp_strength, scale=6)
    y_idx, x_idx = np.indices((height, width), dtype=np.float32)
    warped_x = np.clip(x_idx + dx, 0, width - 1)
    warped_y = np.clip(y_idx + dy, 0, height - 1)

    source_noise = _fractal_noise(width, height, rng, octaves=5,
                                   base_res=4, persistence=0.58, lacunarity=2.1)
    remapped = cv2.remap(source_noise, warped_x, warped_y,
                          interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    dx2, dy2 = _domain_warp(width, height, rng, strength=warp_strength * 0.5, scale=9)
    warped_x2 = np.clip(x_idx + dx2, 0, width - 1)
    warped_y2 = np.clip(y_idx + dy2, 0, height - 1)
    fine_noise = _fractal_noise(width, height, rng, octaves=4,
                                 base_res=8, persistence=0.5, lacunarity=2.3)
    remapped_fine = cv2.remap(fine_noise, warped_x2, warped_y2,
                               interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    blotches = remapped * 0.7 + remapped_fine * 0.3
    b_min, b_max = blotches.min(), blotches.max()
    if b_max > b_min:
        blotches = 2 * (blotches - b_min) / (b_max - b_min) - 1.0
    blotches = blotches * blotch_strength

    Yc, Xc = np.meshgrid(np.linspace(-1, 1, height), np.linspace(-1, 1, width), indexing="ij")
    radial = np.sqrt(Xc ** 2 + Yc ** 2)
    soft_falloff = -0.06 * np.clip(radial - 0.5, 0, None)

    background = base_tone + blotches + soft_falloff

    grain = rng.normal(0, grain_strength, (height, width)).astype(np.float32)
    background = background + grain

    mean_val = background.mean()
    background = mean_val + (background - mean_val) * contrast

    return np.clip(background, 0.0, 1.0).astype(np.float32)


# ============================================================================
# VASKULARNO STABLO 
# ============================================================================

def generate_clean_vessels(width=768, height=768, vessel_contrast=0.5,
                           branching_density=0.5, rng=None):
    if rng is None:
        rng = random.Random(SEED)

    mask = np.zeros((height, width), dtype=np.float32)
    radius_map = np.zeros((height, width), dtype=np.float32)
    
    # KORAK 1: Mapa dubine (depth_map) pronalazi koliko je žila udaljena od ostiuma
    depth_map = np.zeros((height, width), dtype=np.float32)

    def stamp(x, y, r, depth):
        xi, yi = int(round(x)), int(round(y))
        ri = max(1, int(round(r)))
        if 0 <= xi < width and 0 <= yi < height:
            # Ako je na tom pikselu već upisana manja dubina (bliže izvoru), zadrži je
            current_d = depth_map[yi, xi]
            if mask[yi, xi] == 0 or depth < current_d:
                depth_map[yi, xi] = float(depth)
            
            cv2.circle(mask, (xi, yi), ri, 1, -1)
            cv2.circle(radius_map, (xi, yi), ri, float(r), -1)

    def grow_segment(x, y, angle, length, thick, depth, max_depth):
        curr_x, curr_y = x, y
        curr_thick = thick
        n_steps = max(1, int(length))
        thick_end = thick * rng.uniform(0.82, 0.93)

        for i in range(n_steps):
            angle += rng.uniform(-0.16, 0.16)
            curr_x += np.sin(angle) * 1.5
            curr_y += np.cos(angle) * 1.5
            t = i / max(n_steps - 1, 1)
            curr_thick = thick + (thick_end - thick) * t

            if not (0 <= curr_x < width and 0 <= curr_y < height):
                return curr_x, curr_y, angle, curr_thick, False

            stamp(curr_x, curr_y, curr_thick, depth)

        return curr_x, curr_y, angle, thick_end, True

    def branch(x, y, angle, length, thick, depth, max_depth):
        if depth > max_depth or thick < 0.55 or length <= 1:
            return

            
        end_x, end_y, end_angle, end_thick, in_bounds = grow_segment(
            x, y, angle, length, thick, depth, max_depth)
        if not in_bounds:
            return

        depth_factor = depth / max(max_depth, 1)
        if depth < 2:
            end_weight = 0.0
        else:
            end_weight = np.clip((0.04 + 0.45 * depth_factor ** 1.5) / max(branching_density, 0.1), 0.02, 0.85)
        remaining = 1.0 - end_weight
        n_children = rng.choices(
            [2, 3, 1],
            weights=[remaining * 0.73, remaining * 0.27, end_weight]
        )[0]

        if n_children == 1 or depth >= max_depth - 1:
            tip_len = length * rng.uniform(0.35, 0.55)
            grow_segment(end_x, end_y, end_angle, tip_len, end_thick * 0.75, depth, max_depth)
            return

        if n_children == 2:
            f1 = rng.uniform(0.30, 0.70)
            fracs = [f1, 1 - f1]
        else:
            f1 = rng.uniform(0.25, 0.45)
            f2 = rng.uniform(0.20, 0.40)
            f3 = max(0.05, 1 - f1 - f2)
            total = f1 + f2 + f3
            fracs = [f1 / total, f2 / total, f3 / total]

        base_child_len = length * rng.uniform(0.55, 0.72)

        if n_children == 2:
            a1 = np.radians(rng.uniform(25, 65))
            a2 = np.radians(rng.uniform(25, 65))
            angles = [end_angle + a1, end_angle - a2]
        else:
            a1 = np.radians(rng.uniform(25, 65))
            a2 = np.radians(rng.uniform(8, 25))
            a3 = np.radians(rng.uniform(25, 65))
            angles = [end_angle + a1, end_angle - a2, end_angle - a3]

        angles = [
            a + (np.radians(rng.uniform(30, 70)) * rng.choice([-1, 1]) if rng.random() < 0.18 else 0.0)
            for a in angles
        ]
        for frac, child_angle in zip(fracs, angles):
            child_thick = end_thick * (frac ** (1 / 2.7))
            child_len = base_child_len * rng.uniform(0.85, 1.15)
            branch(end_x, end_y, child_angle, child_len, child_thick, depth + 1, max_depth)

    # Pokretanje rekurzije stabla (odmaknuto na h=90 gdje završava kateter)
    initial_angle = np.radians(rng.uniform(-35, 35))
    max_d_param = 5
    branch(width // 2, 90, initial_angle, 95, 6.0, depth=0, max_depth=max_d_param)

    mask_u8 = (mask > 0).astype(np.uint8)
    if mask_u8.sum() == 0:
        return np.zeros((height, width), dtype=np.float32)

    # 2. RADIUS-AWARE SHADING S DUBINSKOM SATURACIJOM
    dist_map = distance_transform_edt(mask_u8)
    local_radius = np.maximum(radius_map, 1.0)
    dist_norm = np.clip(dist_map / local_radius, 0.0, 1.0)

    norm_depth = depth_map / float(max_d_param)
    inner_floor = 0.40 * (norm_depth ** 1.2)  
    edge_sharpness = 0.7

    vessel_profile = np.where(
        mask_u8 > 0,
        inner_floor + (1.0 - inner_floor) * np.exp(-edge_sharpness * dist_norm),
        0.0
    )

    vessel_intensity_fade = 1.0 - 0.15 * norm_depth
    vessel_profile = vessel_profile * vessel_intensity_fade

    vessel_final = gaussian_filter(vessel_profile, sigma=0.6)
    vessel_final = vessel_final * -vessel_contrast

    # 3. KORAK 2: KLINIČKI KATETER
    catheter_layer = np.zeros((height, width), dtype=np.float32)
    catheter_pts = np.array([[width // 2 - 80, 0], [width // 2 - 40, 50], [width // 2, 90]], dtype=np.int32)
    
    cv2.polylines(catheter_layer, [catheter_pts], isClosed=False, color=1.0, thickness=8)
    catheter_layer = cv2.GaussianBlur(catheter_layer, (0, 0), sigmaX=0.8)
    
    vessel_final = np.where(catheter_layer > 0.05, -0.18 * catheter_layer, vessel_final)

    return vessel_final.astype(np.float32)


# ============================================================================
# SILUETA SRCA 
# ============================================================================

def generate_organ_layer(width=768, height=768, enable_anatomy=True, rng=None):

    if not enable_anatomy:
        return np.zeros((height, width), dtype=np.float32)
    if rng is None:
        rng = random.Random(SEED)

    Y, X = np.meshgrid(
        np.linspace(-1, 1, height, dtype=np.float32),
        np.linspace(-1, 1, width, dtype=np.float32),
        indexing="ij"
    )

    random_x_offset = rng.uniform(0.35, 0.55)
    random_y_offset = rng.uniform(0.25, 0.45)

    distortion = 0.07 * np.sin(Y * 3.5) + 0.05 * np.cos(X * 4.5)
    x_obj = X - random_x_offset + distortion
    y_obj = Y - random_y_offset + distortion

    size_x = rng.uniform(0.9, 0.9)
    size_y = rng.uniform(0.9, 0.9)

    heart_shape = (x_obj + y_obj * 0.2) ** 2 / size_x ** 2 + (y_obj) ** 2 / size_y ** 2
    organ_filled = np.where(heart_shape < 1.0, 1.0, 0.0).astype(np.float32)

    outer_gradient = np.clip((heart_shape - 1.0) / 0.2, 0, 1)
    sharp_rim_profile = cv2.GaussianBlur(
        0.08 * (0.5 - outer_gradient) * (0.7 - organ_filled), (0, 0), 15.0)
    anatomy_layer_dark = -0.08 * cv2.GaussianBlur(organ_filled, (0, 0), 4.0)

    return (anatomy_layer_dark + sharp_rim_profile).astype(np.float32)


# ============================================================================
# REBRA -> prikazuje samo sjene koje rebra rade, a ne stvarna rebra
# ============================================================================

def generate_ribs_layer(width=768, height=768, enable_ribs=True, rng=None, rng_np=None):
    if not enable_ribs:
        return np.zeros((height, width), dtype=np.float32)
    if rng is None:
        rng = random.Random(SEED)
    if rng_np is None:
        rng_np = np.random.RandomState(SEED)

    y_indices, x_indices = np.indices((height, width), dtype=np.float32)
    ribs_mask = np.zeros((height, width), dtype=np.float32)

    spacing = 135      
    thickness = 58    
    base_darkness = rng.uniform(0.05, 0.09) 

    warp_noise = rng_np.randn(8, 8).astype(np.float32)
    warp_noise = cv2.resize(warp_noise, (width, height), interpolation=cv2.INTER_CUBIC)
    warp_noise = gaussian_filter(warp_noise, sigma=30.0) * 25.0 # Snaga distorzije u pikselima

    warped_y = y_indices + warp_noise

    for i in range(-2, 6):
    
        rib_center_line = (i * spacing) + 140 + (0.0007 * (x_indices - width / 2) ** 2) + (0.15 * x_indices)
        
        dist_to_rib = np.abs(warped_y - rib_center_line)
        
        rib_profile = np.where(dist_to_rib < thickness, (1.0 - (dist_to_rib / thickness) ** 2), 0.0)
        
        ribs_mask = np.maximum(ribs_mask, rib_profile)

    fade_gradient = (x_indices * 0.6 - y_indices * 0.2) / width
    fade_mask = np.clip(1.2 - fade_gradient, 0.0, 1.0)
    
    final_ribs = ribs_mask * base_darkness * fade_mask

    return -cv2.GaussianBlur(final_ribs, (0, 0), sigmaX=12.0).astype(np.float32)


# ============================================================================
# VINJETIRANJE
# ============================================================================

def apply_vignetting(image, intensity=0.25):
    """Simulira pad svjetline na rubovima rendgenskog detektora (vinjetiranje)."""
    h, w = image.shape
    y_indices, x_indices = np.indices((h, w), dtype=np.float32)
    x_c, y_c = w / 2.0, h / 2.0
    r_max_sq = (w / 2.0) ** 2 + (h / 2.0) ** 2

    vignette = 1.0 - intensity * (((x_indices - x_c) ** 2 + (y_indices - y_c) ** 2) / r_max_sq)
    return image * vignette


# ============================================================================
# GLAVNI PIPELINE
# ============================================================================

def generate_angiogram(img_size=(512, 512),
                        seed=SEED,
                        vessel_contrast=0.3,
                        branching_density=1.0,
                        noise_level=0.02,
                        blur_sigma=0.0,
                        motion_blur_size=2,
                        enable_anatomy=True,
                        enable_ribs=True,
                        vignette_intensity=0.15,
                        bg_blotch_strength=0.11,
                        bg_warp_strength=28):
    """
    Glavni algoritam koji na temelju skupa parametara generira konacnu sliku
    angiograma. 'seed' kontrolira SVE nasumicne komponente (pozadinu, zile,
    organ, sum) -- razlicit seed po slici garantira da generirane
    slike budu stvarno razlicite, ne identicne kopije s drugim sumom.
    """
    h, w = img_size
    rng_py = random.Random(seed)
    rng_np = np.random.RandomState(seed)

    back = generate_angiogram_background(
        w, h, seed=seed,
        blotch_strength=bg_blotch_strength,
        warp_strength=bg_warp_strength,
    )

    vessel_layer = generate_clean_vessels(w, h, vessel_contrast, branching_density, rng=rng_py)
    anatomy_layer = generate_organ_layer(w, h, enable_anatomy, rng=rng_py)
    ribs_layer = generate_ribs_layer(w, h, enable_ribs, rng=rng_py, rng_np=rng_np)

    combined = 1.5 * back + 1.6 * anatomy_layer + 1.4 * ribs_layer + vessel_layer
    combined = np.clip(combined, 0.0, 1.0)

    signal_dependent_noise = np.sqrt(combined) * rng_np.normal(0, noise_level, (h, w)).astype(np.float32)
    detector_grain = rng_np.normal(0, 0.012, (h, w)).astype(np.float32)
    combined = combined + signal_dependent_noise + detector_grain

    if blur_sigma > 0:
        combined = gaussian_filter(combined, sigma=blur_sigma)

    if vignette_intensity > 0:
        combined = apply_vignetting(combined, intensity=vignette_intensity)

    if motion_blur_size > 1:
        kernel_motion = np.zeros((motion_blur_size, motion_blur_size), dtype=np.float32)
        np.fill_diagonal(kernel_motion, 1)
        if kernel_motion.sum() > 0:
            kernel_motion /= kernel_motion.sum()
            combined = cv2.filter2D(combined, -1, kernel_motion)

    combined = np.clip(combined, 0.0, 1.0)

    return np.clip(combined, 0.0, 1.0)


# ============================================================================
# GENERIRANJE 10 RAZLICITIH ANGIOGRAMA (svaki sa svojim seedom)
# ============================================================================

NUM_SAMPLES = 10
BASE_SEED = 100 

if __name__ == "__main__":
    fig, axes = plt.subplots(2, 5, figsize=(20, 9))
    axes = axes.ravel()

    print(f"Generiram {NUM_SAMPLES} razlicitih sintetskih angiograma...")

    for idx in range(NUM_SAMPLES):
        sample_seed = BASE_SEED + idx * 7919  

        img = generate_angiogram(
            img_size=(512, 512),
            seed=sample_seed,
            vessel_contrast=0.3,
            branching_density=1.0,
            noise_level=0.02,
            motion_blur_size=2,
            enable_anatomy=True,
            enable_ribs=True,
            vignette_intensity=0.15,
        )

        axes[idx].imshow(img, cmap="gray", vmin=0, vmax=1)
        axes[idx].set_title(f"Uzorak {idx + 1} (seed={sample_seed})",
                             fontsize=11, fontweight="bold", color="#1B365D", pad=8)
        axes[idx].axis("off")


    plt.tight_layout()
    plt.subplots_adjust(top=0.90, hspace=0.35, wspace=0.12)
    fig.suptitle("Proceduralni simulator angiograma: 10 nezavisno generiranih primjera",
                 fontsize=16, fontweight="bold", color="#1B365D")

    plt.show()