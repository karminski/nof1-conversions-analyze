import os
import json
import hashlib
import shutil
import argparse
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Configuration
INPUT_DIR = "conversions"
OUTPUT_DIR = "conversions_deduped"
REPORT_FILE = "deduplication_report.json"
PROGRESS_INTERVAL = 500

# Thread-safe lock
data_lock = Lock()


def calculate_md5(filepath: str) -> Tuple[str, str]:
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            # Read file in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return filepath, hash_md5.hexdigest()
    except Exception as e:
        print(f"Error calculating MD5 for {filepath}: {e}")
        return filepath, None


def print_progress_bar(
    completed: int, total: int, bar_length: int = 50, start_time: float = None
):
    """Print a progress bar"""
    percent = completed / total
    filled = int(bar_length * percent)
    bar = "█" * filled + "-" * (bar_length - filled)

    elapsed = time.time() - start_time if start_time else 0
    rate = completed / elapsed if elapsed > 0 else 0
    remaining = (total - completed) / rate if rate > 0 else 0

    print(
        f"\r[{bar}] {completed:,}/{total:,} ({percent*100:.1f}%) | "
        f"{rate:.1f} files/sec | ETA: {remaining/60:.1f} min",
        end="",
        flush=True,
    )


def scan_and_hash_files(input_dir: str, num_threads: int = 4) -> Dict[str, List[str]]:
    """Scan all JSON files and calculate their MD5 hashes"""
    print("=" * 60)
    print("STEP 1: SCANNING AND HASHING FILES")
    print("=" * 60)

    # Get all JSON files
    all_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".json"):
                all_files.append(os.path.join(root, file))

    total_files = len(all_files)
    print(f"Found {total_files:,} JSON files")
    print(f"Using {num_threads} threads for hashing")
    print("Calculating MD5 hashes...")
    print()

    # Dictionary to store: md5_hash -> [list of filepaths]
    hash_to_files = defaultdict(list)
    completed = 0
    errors = []

    start_time = time.time()

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_file = {
            executor.submit(calculate_md5, filepath): filepath for filepath in all_files
        }

        for future in as_completed(future_to_file):
            completed += 1

            filepath, md5_hash = future.result()

            if md5_hash:
                with data_lock:
                    hash_to_files[md5_hash].append(filepath)
            else:
                errors.append(filepath)

            # Update progress
            if completed % PROGRESS_INTERVAL == 0 or completed == total_files:
                print_progress_bar(completed, total_files, start_time=start_time)

    # Final progress update
    print_progress_bar(total_files, total_files, start_time=start_time)
    print()

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("HASHING COMPLETE")
    print("=" * 60)
    print(f"Files processed: {total_files:,}")
    print(f"Unique files: {len(hash_to_files):,}")
    print(f"Duplicate files: {total_files - len(hash_to_files):,}")
    print(f"Processing time: {elapsed/60:.1f} minutes")
    print(f"Errors: {len(errors)}")

    if errors:
        print(f"\nFiles with errors (first 10):")
        for error_file in errors[:10]:
            print(f"  - {error_file}")

    return dict(hash_to_files), errors


def copy_unique_files(
    hash_to_files: Dict[str, List[str]], output_dir: str
) -> Tuple[List[str], List[str]]:
    """Copy unique files to output directory"""
    print("\n" + "=" * 60)
    print("STEP 2: COPYING UNIQUE FILES")
    print("=" * 60)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    copied_files = []
    duplicate_files = []

    for idx, (md5_hash, files) in enumerate(hash_to_files.items(), 1):
        if idx % 100 == 0:
            print(f"Processing: {idx:,}/{len(hash_to_files):,} unique files")

        # Keep the first file (typically the oldest based on filename)
        files_sorted = sorted(files)
        file_to_keep = files_sorted[0]

        # Copy the file
        source_path = file_to_keep
        dest_filename = os.path.basename(file_to_keep)
        dest_path = os.path.join(output_dir, dest_filename)

        try:
            shutil.copy2(source_path, dest_path)
            copied_files.append(file_to_keep)

            # Record duplicates
            if len(files) > 1:
                for dup_file in files_sorted[1:]:
                    duplicate_files.append(dup_file)

        except Exception as e:
            print(f"Error copying {source_path}: {e}")

    print("\n" + "=" * 60)
    print("COPYING COMPLETE")
    print("=" * 60)
    print(f"Unique files copied: {len(copied_files):,}")
    print(f"Duplicate files skipped: {len(duplicate_files):,}")

    return copied_files, duplicate_files


def calculate_size_savings(original_files: List[str], duplicate_files: List[str]):
    """Calculate space savings from deduplication"""
    print("\n" + "=" * 60)
    print("SPACE SAVINGS ANALYSIS")
    print("=" * 60)

    original_size = 0
    for filepath in original_files:
        try:
            original_size += os.path.getsize(filepath)
        except:
            pass

    duplicate_size = 0
    for filepath in duplicate_files:
        try:
            duplicate_size += os.path.getsize(filepath)
        except:
            pass

    print(f"Original total size: {original_size / 1024 / 1024 / 1024:.2f} GB")
    print(
        f"Duplicate files size: {duplicate_size / 1024 / 1024 / 1024:.2f} GB (saved)"
    )
    print(
        f"Remaining size: {(original_size - duplicate_size) / 1024 / 1024 / 1024:.2f} GB"
    )
    print(f"Space reduction: {duplicate_size / original_size * 100:.1f}%")

    return original_size, duplicate_size


def generate_report(
    hash_to_files: Dict[str, List[str]],
    copied_files: List[str],
    duplicate_files: List[str],
    errors: List[str],
    original_size: int,
    duplicate_size: int,
    output_file: str,
):
    """Generate deduplication report"""
    print("\n" + "=" * 60)
    print("GENERATING REPORT")
    print("=" * 60)

    # Find files with most duplicates
    duplicates_sorted = sorted(
        [(md5, files) for md5, files in hash_to_files.items() if len(files) > 1],
        key=lambda x: len(x[1]),
        reverse=True,
    )

    report = {
        "summary": {
            "total_files_scanned": sum(len(files) for files in hash_to_files.values()),
            "unique_files": len(hash_to_files),
            "duplicate_files": len(duplicate_files),
            "files_copied": len(copied_files),
            "errors": len(errors),
            "original_size_gb": original_size / 1024 / 1024 / 1024,
            "duplicate_size_gb": duplicate_size / 1024 / 1024 / 1024,
            "space_reduction_percent": (
                duplicate_size / original_size * 100 if original_size > 0 else 0
            ),
        },
        "top_duplicates": [
            {
                "md5": md5,
                "count": len(files),
                "files": files,
                "kept": files[0],
                "removed": files[1:],
            }
            for md5, files in duplicates_sorted[:20]
        ],
        "error_files": errors[:100],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Report saved: {output_file}")

    # Print top duplicates
    if duplicates_sorted:
        print("\nTop 5 files with most duplicates:")
        for md5, files in duplicates_sorted[:5]:
            print(f"  - {len(files)} copies: {os.path.basename(files[0])}")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Deduplicate JSON files based on MD5 hash",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deduplicate_files.py                                    # Use defaults
  python deduplicate_files.py --threads 8                        # Use 8 threads
  python deduplicate_files.py --input conversions --output conversions_deduped
        """,
    )

    parser.add_argument(
        "--threads",
        "-t",
        type=int,
        default=4,
        help="Number of threads for parallel processing (default: 4)",
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=INPUT_DIR,
        help=f"Input directory containing JSON files (default: {INPUT_DIR})",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=OUTPUT_DIR,
        help=f"Output directory for deduplicated files (default: {OUTPUT_DIR})",
    )

    parser.add_argument(
        "--report",
        "-r",
        type=str,
        default=REPORT_FILE,
        help=f"Report output file (default: {REPORT_FILE})",
    )

    return parser.parse_args()


def main():
    """Main execution function"""
    args = parse_arguments()

    print("=" * 60)
    print("FILE DEDUPLICATION TOOL")
    print("=" * 60)
    print(f"Input directory: {args.input}")
    print(f"Output directory: {args.output}")
    print(f"Report file: {args.report}")
    print(f"Threads: {args.threads}")
    print("=" * 60)

    overall_start = time.time()

    try:
        # Step 1: Scan and hash all files
        hash_to_files, errors = scan_and_hash_files(args.input, args.threads)

        # Get all original files for size calculation
        all_original_files = []
        for files in hash_to_files.values():
            all_original_files.extend(files)

        # Step 2: Copy unique files
        copied_files, duplicate_files = copy_unique_files(hash_to_files, args.output)

        # Step 3: Calculate savings
        original_size, duplicate_size = calculate_size_savings(
            all_original_files, duplicate_files
        )

        # Step 4: Generate report
        generate_report(
            hash_to_files,
            copied_files,
            duplicate_files,
            errors,
            original_size,
            duplicate_size,
            args.report,
        )

        overall_time = time.time() - overall_start

        print("\n" + "=" * 60)
        print("DEDUPLICATION COMPLETE!")
        print("=" * 60)
        print(f"Total execution time: {overall_time/60:.1f} minutes")
        print(f"Unique files saved to: {args.output}/")
        print(f"Deduplication report: {args.report}")
        print("\nNext steps:")
        print(
            f"1. Use '{args.output}' as input for clean_trading_data.py --input {args.output}"
        )
        print("2. Review deduplication report for details")

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
    except Exception as e:
        print(f"\nERROR during processing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

