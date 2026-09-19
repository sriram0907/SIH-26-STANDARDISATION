"""
Convenience Launcher
=====================
Generates data (if needed), starts FastAPI, runs pipeline, launches Streamlit.

Usage:
    python run.py              # Full launch (API + pipeline + Streamlit)
    python run.py --data-only  # Just generate synthetic data
    python run.py --api-only   # Just start the API server
"""

import os
import sys
import subprocess
import time
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def generate_data():
    """Generate synthetic data if it doesn't exist."""
    csv_path = os.path.join(PROJECT_DIR, "data", "cpse_variants.csv")
    if not os.path.exists(csv_path):
        logger.info("📦 Generating synthetic dataset...")
        from generate_data import generate_dataset
        generate_dataset(os.path.join(PROJECT_DIR, "data"))
    else:
        logger.info(f"📂 Dataset already exists: {csv_path}")


def start_api_server():
    """Start the FastAPI server in background."""
    logger.info("🚀 Starting FastAPI server on http://localhost:8000 ...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    # Give it a moment to start
    time.sleep(3)
    if process.poll() is not None:
        logger.error("❌ API server failed to start!")
        output = process.stdout.read().decode() if process.stdout else ""
        logger.error(output)
        sys.exit(1)
    logger.info("✅ API server started (PID: %d)", process.pid)
    return process


def run_pipeline():
    """Run the harmonization pipeline."""
    logger.info("⚙️ Running harmonization pipeline...")
    from backend.pipeline import run_pipeline as _run
    result = _run(os.path.join(PROJECT_DIR, "data", "cpse_variants.csv"))
    logger.info(f"✅ Pipeline complete: {result}")
    return result


def start_streamlit():
    """Launch Streamlit UI."""
    logger.info("🌐 Launching Streamlit on http://localhost:8501 ...")
    app_path = os.path.join(PROJECT_DIR, "app.py")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", app_path,
         "--server.port", "8501", "--server.headless", "true"],
        cwd=PROJECT_DIR,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Material Code Harmonization Platform Launcher")
    parser.add_argument("--data-only", action="store_true", help="Only generate synthetic data")
    parser.add_argument("--api-only", action="store_true", help="Only start the API server")
    parser.add_argument("--skip-pipeline", action="store_true", help="Skip running the pipeline")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Material Code Harmonization Platform")
    logger.info("=" * 60)

    # Step 1: Generate data
    generate_data()

    if args.data_only:
        logger.info("Done (data-only mode)")
        sys.exit(0)

    # Step 2: Start API server
    api_process = start_api_server()

    if args.api_only:
        logger.info("API-only mode. Press Ctrl+C to stop.")
        try:
            api_process.wait()
        except KeyboardInterrupt:
            api_process.terminate()
        sys.exit(0)

    try:
        # Step 3: Run pipeline
        if not args.skip_pipeline:
            run_pipeline()

        # Step 4: Launch Streamlit
        start_streamlit()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        api_process.terminate()
        logger.info("✅ Shutdown complete")
