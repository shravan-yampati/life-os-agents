"""Ingestion Tracker — sorts incoming documents into correct buckets securely."""

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

from src.providers.factory import ProviderFactory

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _REPO_ROOT / ".raglab" / "ingest_manifest.json"
_DATA_DIR = _REPO_ROOT / "data"

VALID_TYPES = ["bank_statement", "tax_document", "general_receipt", "unknown"]


def get_file_hash(filepath: Path) -> str:
    """Computes SHA-256 hash of a file to detect duplicates."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_manifest(manifest: dict, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def classify_document(filepath: Path) -> str:
    """Uses LLM to classify document strictly based on filename and type."""
    llm = ProviderFactory.get_llm()
    
    # In a full system we'd extract text from the PDF here. 
    # For now, we use filename heuristics via LLM.
    prompt = (
        f"You are a document classifier. Look at the filename: '{filepath.name}'.\n"
        f"Classify it into EXACTLY ONE of these categories: {VALID_TYPES}.\n"
        f"Return ONLY the category name as a raw string."
    )
    
    try:
        # max_tokens must be generous: gemini-2.5-flash spends "thinking" tokens from
        # this same budget, so a tiny limit returns an empty string (always "unknown").
        response = llm.generate(prompt, temperature=0.1, max_tokens=2048).strip().lower()
        # Clean up any potential quotes or markdown
        response = response.replace('"', '').replace("'", "").replace("`", "")
        if response in VALID_TYPES:
            return response
    except Exception:
        pass
        
    return "unknown"


def ingest(filepath: Path, manifest_path: Path = _MANIFEST_PATH, data_dir: Path = _DATA_DIR) -> dict:
    """Processes a file: hashes it, classifies it, moves it, and updates manifest."""
    if not filepath.exists() or not filepath.is_file():
        raise FileNotFoundError(f"File not found: {filepath}")
        
    file_hash = get_file_hash(filepath)
    manifest = load_manifest(manifest_path)
    
    if file_hash in manifest:
        return {
            "status": "skipped",
            "reason": "duplicate",
            "file_hash": file_hash,
            "manifest_entry": manifest[file_hash]
        }
        
    doc_type = classify_document(filepath)
    
    # Route to subfolder
    subfolder_map = {
        "bank_statement": "finance",
        "tax_document": "taxes",
        "general_receipt": "receipts",
        "unknown": "uncategorized"
    }
    
    dest_dir = data_dir / subfolder_map.get(doc_type, "uncategorized")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepend date to prevent naming collisions just in case
    today_str = datetime.date.today().isoformat()
    clean_name = f"{today_str}_{filepath.name}"
    dest_path = dest_dir / clean_name
    
    shutil.copy2(filepath, dest_path)
    
    entry = {
        "original_filename": filepath.name,
        "date_processed": datetime.datetime.now().isoformat(),
        "type": doc_type,
        "dest_path": ""
    }
    
    # Fix the relative path logic for tests
    try:
        entry["dest_path"] = str(dest_path.relative_to(_REPO_ROOT).as_posix())
    except ValueError:
        entry["dest_path"] = str(dest_path.as_posix())
    
    manifest[file_hash] = entry
    save_manifest(manifest, manifest_path)
    
    return {
        "status": "success",
        "file_hash": file_hash,
        "manifest_entry": entry
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
        
    parser = argparse.ArgumentParser(description="Ingest a document into Life OS.")
    parser.add_argument("command", choices=["ingest"])
    parser.add_argument("--file", required=True, help="Path to file to ingest")
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        filepath = Path(args.file)
        try:
            result = ingest(filepath)
            if result["status"] == "skipped":
                print(f"Skipped duplicate file. Already processed as '{result['manifest_entry']['type']}'.")
            else:
                entry = result["manifest_entry"]
                print(f"Successfully ingested as: {entry['type']}")
                print(f"Stored at: {entry['dest_path']}")
        except Exception as e:
            print(f"Error ingesting file: {e}")

if __name__ == "__main__":
    main()
