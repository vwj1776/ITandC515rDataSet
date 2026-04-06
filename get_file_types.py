import os
import sys
from collections import defaultdict
import shutil

# Try to import matplotlib for visualization
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

def get_size_format(b, factor=1024, suffix="B"):
    """
    Scale bytes to its proper byte format
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"

def analyze_directory(directory):
    """
    Traverses a directory and collects file info for each file type.
    """
    file_data = defaultdict(list)
    for root, dirs, files in os.walk(directory):
        for file in files:
            try:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file)
                if ext:
                    clean_ext = ext.lstrip('.').lower()
                    size = os.path.getsize(file_path)
                    file_data[clean_ext].append({'path': file_path, 'size': size})
            except OSError:
                continue
    return file_data

def get_stats_from_data(file_data):
    stats = defaultdict(lambda: {'count': 0, 'sizes': []})
    for ext, files in file_data.items():
        stats[ext]['count'] = len(files)
        stats[ext]['sizes'] = [f['size'] for f in files]
    return stats

def create_sample(file_data, output_dir, sample_rate=0.1):
    if os.path.exists(output_dir):
        print(f"Cleaning up existing sample directory: {output_dir}")
        shutil.rmtree(output_dir)
    
    os.makedirs(output_dir)
    print(f"Creating sample in: {output_dir}")
    
    # --- HARD CODED THRESHOLDS (UPDATED) ---
    # INCREASED to 25MB to catch 'csv' (21MB) and 'js' (5.2MB)
    MIN_TOTAL_SIZE_MB = 25  
    # If a file type has fewer than 20 files, take ALL of them.
    MIN_FILE_COUNT = 20
    # ---------------------------------------

    total_files_copied = 0
    
    for ext, files in file_data.items():
        # Calculate stats for this extension first
        total_size_bytes = sum(f['size'] for f in files)
        count = len(files)
        
        # Sort by size to ensure proportional size sampling (for the big files)
        files.sort(key=lambda x: x['size'])
        
        # --- LOGIC: Check for Small/Medium Data ---
        # If total size is small (e.g. csv, js), just take 100% to avoid sampling errors
        if total_size_bytes < (MIN_TOTAL_SIZE_MB * 1024 * 1024) or count < MIN_FILE_COUNT:
            sample_files = files[:] 
            print(f"  {ext}: Small/Medium dataset ({get_size_format(total_size_bytes)}) -> Taking 100%")
        else:
            # Standard Systematic Sampling (Every Nth file)
            step = int(1 / sample_rate)
            if step < 1: step = 1
            sample_files = files[::step]
        
        if not sample_files:
            continue
            
        # Create extension folder
        ext_dir = os.path.join(output_dir, ext)
        os.makedirs(ext_dir, exist_ok=True)
        
        for f in sample_files:
            src = f['path']
            filename = os.path.basename(src)
            dst = os.path.join(ext_dir, filename)
            
            # Handle duplicate filenames
            counter = 1
            while os.path.exists(dst):
                name, extension = os.path.splitext(filename)
                dst = os.path.join(ext_dir, f"{name}_{counter}{extension}")
                counter += 1
            
            try:
                shutil.copy2(src, dst)
                total_files_copied += 1
            except Exception as e:
                print(f"Error copying {filename}: {e}")
            
    print(f"\nSample creation complete. Copied {total_files_copied} files.\n")

def print_table(stats):
    if not stats:
        print("No files found.")
        return

    headers = ["Extension", "Count", "Total Size", "Min Size", "Max Size", "Avg Size"]
    col_widths = [12, 10, 15, 15, 15, 15]
    header_format = " | ".join([f"{{:<{w}}}" for w in col_widths])
    separator = "-+-".join(["-" * w for w in col_widths])

    print(header_format.format(*headers))
    print(separator)

    for ext, data in sorted(stats.items(), key=lambda item: item[1]['count'], reverse=True):
        count = data['count']
        sizes = data['sizes']
        total_size = sum(sizes)
        min_size = min(sizes)
        max_size = max(sizes)
        avg_size = total_size / count if count else 0

        print(header_format.format(
            ext, count, get_size_format(total_size),
            get_size_format(min_size), get_size_format(max_size), get_size_format(avg_size)
        ))

def visualize_data(stats):
    if not MATPLOTLIB_AVAILABLE:
        print("\n[!] matplotlib is not installed. Skipping visualization.")
        return

    if not stats:
        return

    sorted_items = sorted(stats.items(), key=lambda item: item[1]['count'], reverse=True)
    extensions = [item[0] for item in sorted_items]
    counts = [item[1]['count'] for item in sorted_items]
    total_sizes_mb = [sum(item[1]['sizes']) / (1024 * 1024) for item in sorted_items]

    fig, ax1 = plt.subplots(figsize=(14, 7))

    color = 'tab:blue'
    ax1.set_xlabel('File Extension')
    ax1.set_ylabel('Count', color=color)
    bars = ax1.bar(extensions, counts, color=color, alpha=0.6, label='Count')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.tick_params(axis='x', rotation=45)

    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Total Size (MB)', color=color)
    line = ax2.plot(extensions, total_sizes_mb, color=color, marker='o', linestyle='-', linewidth=2, label='Total Size (MB)')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title('File Types: Count vs Total Size')
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right')

    fig.tight_layout()
    plt.show()

def compare_datasets(stats_og, stats_sample, target_ratio=0.1):
    print(f"\nComparing Original vs Sample (Target Ratio: {target_ratio:.1%})")
    
    headers = ["Extension", "OG Size", "Sample Size", "Actual Ratio", "Deviation"]
    col_widths = [12, 15, 15, 15, 15]
    header_format = " | ".join([f"{{:<{w}}}" for w in col_widths])
    separator = "-+-".join(["-" * w for w in col_widths])
    
    print(header_format.format(*headers))
    print(separator)
    
    all_extensions = set(stats_og.keys()) | set(stats_sample.keys())
    total_og_size = 0
    total_sample_size = 0

    for ext in sorted(all_extensions):
        og_size = sum(stats_og[ext]['sizes']) if ext in stats_og else 0
        sample_size = sum(stats_sample[ext]['sizes']) if ext in stats_sample else 0
        
        total_og_size += og_size
        total_sample_size += sample_size

        if og_size > 0:
            ratio = sample_size / og_size
            deviation = ratio - target_ratio
            
            # Special indicator for 100% copy
            if ratio > 0.98: 
                ratio_str = "100% (ALL)"
                deviation_str = "N/A"
            else:
                ratio_str = f"{ratio:.2%}"
                deviation_str = f"{deviation:+.2%}"
        else:
            ratio_str = "N/A"
            deviation_str = "N/A"
            
        print(header_format.format(
            ext, get_size_format(og_size), get_size_format(sample_size),
            ratio_str, deviation_str
        ))
    
    print(separator)
    if total_og_size > 0:
        total_ratio = total_sample_size / total_og_size
        total_deviation = total_ratio - target_ratio
        print(header_format.format(
            "TOTAL", get_size_format(total_og_size), get_size_format(total_sample_size),
            f"{total_ratio:.2%}", f"{total_deviation:+.2%}"
        ))
    print("\n")


if __name__ == "__main__":
    # --- CONFIGURATION ---
    # CHANGE THIS to your folder path
    target_folder = r"c:\Users\vj234\Desktop\data_set"
    # ---------------------

    if len(sys.argv) > 1:
        target_folder = sys.argv[1]

    if os.path.exists(target_folder):
        print(f"Analyzing Source: '{target_folder}'...\n")
        file_data = analyze_directory(target_folder)
        statsOgFolder = get_stats_from_data(file_data)
        print_table(statsOgFolder)
        
        # Create sample folder name
        parent_dir = os.path.dirname(os.path.normpath(target_folder))
        sample_dir = os.path.join(parent_dir, "NapierOne_Sample")
        
        # Run Creation
        create_sample(file_data, sample_dir, sample_rate=0.1)
        
        if os.path.exists(sample_dir):
            print(f"\nAnalyzing Sample '{sample_dir}'...\n")
            statsSampleFolder = get_stats_from_data(analyze_directory(sample_dir))
            print_table(statsSampleFolder)
            compare_datasets(statsOgFolder, statsSampleFolder)
            visualize_data(statsSampleFolder)
            visualize_data(statsOgFolder)
    else:
        print(f"The folder '{target_folder}' was not found.")