"""Utility script to download quantized Shieldstral GGUF model from Hugging Face."""
import argparse
import os
import sys
import urllib.request
from pathlib import Path

DEFAULT_HF_REPO = "Abiray/Shieldstral-1.0-3B-GGUF"
DEFAULT_FILENAME = "Shieldstral-1.0-3B-Q4_K_M.gguf"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def download_hf_model(repo_id: str = DEFAULT_HF_REPO, filename: str = DEFAULT_FILENAME, output_dir: Path = MODELS_DIR):
    """Downloads model file from Hugging Face using huggingface_hub with fast hf_transfer."""
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = output_dir / filename

    if target_path.exists():
        print(f"[Info] Model already exists at: {target_path} ({target_path.stat().st_size / (1024*1024):.1f} MB)")
        return target_path

    print(f"[Info] Downloading {filename} from {repo_id}...")
    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(output_dir),
            local_dir_use_symlinks=False
        )
        print(f"[Success] Model saved to: {downloaded}")
        return Path(downloaded)
    except ImportError:
        # Fallback to direct download via urllib
        url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        print(f"[Info] huggingface_hub not found. Downloading directly from: {url}")
        
        def reporthook(blocknum, blocksize, totalsize):
            readsofar = blocknum * blocksize
            if totalsize > 0:
                percent = readsofar * 1e2 / totalsize
                s = f"\rDownloading: {percent:5.1f}% ({readsofar / (1024*1024):.1f} / {totalsize / (1024*1024):.1f} MB)"
                sys.stdout.write(s)
                sys.stdout.flush()

        urllib.request.urlretrieve(url, target_path, reporthook=reporthook)
        print(f"\n[Success] Model saved to: {target_path}")
        return target_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Shieldstral GGUF model")
    parser.add_argument("--repo", type=str, default=DEFAULT_HF_REPO, help="HuggingFace repository ID")
    parser.add_argument("--filename", type=str, default=DEFAULT_FILENAME, help="GGUF filename")
    parser.add_argument("--output-dir", type=str, default=str(MODELS_DIR), help="Output directory")
    args = parser.parse_args()

    download_hf_model(repo_id=args.repo, filename=args.filename, output_dir=Path(args.output_dir))
