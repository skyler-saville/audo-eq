from __future__ import annotations

import argparse
from pathlib import Path

from .core import MasteringPipeline, build_chain_from_config, create_tra_chain
from .io.audio_file import read_audio, write_audio
from .utils.config import load_chain_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Audo_EQ CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    master_parser = subparsers.add_parser("master", help="Master a target track")
    master_parser.add_argument("--target", required=True, help="Path to target audio")
    master_parser.add_argument(
        "--reference", required=True, help="Path to reference audio"
    )
    master_parser.add_argument("--output", required=True, help="Path to output audio")
    master_parser.add_argument(
        "--config", help="Optional chain config (YAML or JSON)"
    )

    process_parser = subparsers.add_parser(
        "process", help="Alias for 'master' command"
    )
    process_parser.add_argument("--target", required=True, help="Path to target audio")
    process_parser.add_argument(
        "--reference", required=True, help="Path to reference audio"
    )
    process_parser.add_argument("--output", required=True, help="Path to output audio")
    process_parser.add_argument(
        "--config", help="Optional chain config (YAML or JSON)"
    )

    args = parser.parse_args()
    _run_mastering(
        target_path=Path(args.target),
        reference_path=Path(args.reference),
        output_path=Path(args.output),
        config_path=Path(args.config) if args.config else None,
    )


def _run_mastering(
    target_path: Path,
    reference_path: Path,
    output_path: Path,
    config_path: Path | None,
) -> None:
    target_audio, target_sr = read_audio(target_path)
    reference_audio, reference_sr = read_audio(reference_path)
    if target_sr != reference_sr:
        raise ValueError("Target and reference sample rates must match.")

    if config_path is None:
        chain = create_tra_chain(target_audio, reference_audio, target_sr)
    else:
        config = load_chain_config(config_path)
        chain = build_chain_from_config(config, reference_audio, target_sr)

    pipeline = MasteringPipeline(chain)
    mastered = pipeline.run(target_audio, target_sr)
    write_audio(output_path, mastered, target_sr)


if __name__ == "__main__":
    main()
