from __future__ import annotations

"""Compare the local replay with an external official-runner adapter.

The exact AlgoMada Java CLI/output contract was not available when v0.13.0 was
built.  This script therefore uses a tiny stable adapter protocol: the external
command receives paths through placeholders and must print a JSON object with
any of the final fields listed in COMPARED_FIELDS.  Once the official Java
repository is published, either call it directly if it can emit that JSON or
wrap it with a few lines that translate its output.

Example:
    python scripts/differential_runner.py \
      --map maps/official_sample.txt \
      --elevation maps/official_sample_elevation.txt \
      --actions output/example_actions.txt \
      --runner-cmd 'java -jar runner.jar --map {map} --elevation {elevation} --actions {actions} --json'
"""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine.actions_parser import parse_actions_text
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator


COMPARED_FIELDS = (
    "score",
    "secured_chests",
    "lost_chests",
    "hero_stones",
    "remaining_time",
    "total_stamina",
    "total_battery",
)


def local_final(map_path: Path, elevation_path: Path | None, actions_path: Path) -> dict[str, int]:
    map_text = map_path.read_text(encoding="utf-8")
    elevation_text = elevation_path.read_text(encoding="utf-8") if elevation_path else None
    game_map = MapParser.parse(map_text, elevation_text=elevation_text)
    actions = parse_actions_text(actions_path.read_text(encoding="utf-8"), time_limit=game_map.time_limit)
    state = MapParser.build_initial_state(game_map)
    result = Simulator(state).run_actions(actions)
    snap = result.final_snapshot
    score_inputs = snap["score_inputs"]
    props = snap["props"]
    return {
        "score": int(result.score),
        "secured_chests": int(score_inputs["secured_chests"]),
        "lost_chests": int(props["lost_chests"]),
        "hero_stones": int(score_inputs["hero_stones"]),
        "remaining_time": int(snap["remaining_time"]),
        "total_stamina": int(score_inputs["total_stamina"]),
        "total_battery": int(score_inputs["total_battery"]),
    }


def _extract_json(stdout: str) -> dict[str, object]:
    # Prefer a full JSON stdout. If the runner logs before it, accept the last
    # line that is itself a JSON object so a wrapper can stay simple.
    text = stdout.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Le runner externe n'a pas produit d'objet JSON exploitable.")


def external_final(template: str, map_path: Path, elevation_path: Path | None, actions_path: Path) -> dict[str, object]:
    command = template.format(
        map=str(map_path.resolve()),
        elevation=str(elevation_path.resolve()) if elevation_path else "",
        actions=str(actions_path.resolve()),
    )
    completed = subprocess.run(
        shlex.split(command),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Runner externe terminé avec code {completed.returncode}.\n"
            f"stderr:\n{completed.stderr.strip()}"
        )
    return _extract_json(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Differential check local Simulator vs official runner adapter")
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--elevation", type=Path)
    parser.add_argument("--actions", required=True, type=Path)
    parser.add_argument(
        "--runner-cmd",
        help="Commande externe avec placeholders {map}, {elevation}, {actions}. Sans cette option, affiche seulement la référence locale.",
    )
    args = parser.parse_args()

    local = local_final(args.map, args.elevation, args.actions)
    print(json.dumps({"local": local}, ensure_ascii=False, indent=2))
    if not args.runner_cmd:
        print("Aucun runner externe fourni: comparaison différentielle non exécutée.")
        return 0

    external = external_final(args.runner_cmd, args.map, args.elevation, args.actions)
    differences: dict[str, dict[str, object]] = {}
    for field in COMPARED_FIELDS:
        if field not in external:
            continue
        try:
            ext_value = int(external[field])
        except (TypeError, ValueError):
            differences[field] = {"local": local[field], "external": external[field]}
            continue
        if local[field] != ext_value:
            differences[field] = {"local": local[field], "external": ext_value}

    print(json.dumps({"external": external, "differences": differences}, ensure_ascii=False, indent=2))
    if differences:
        print("DIVERGENCE détectée.", file=sys.stderr)
        return 2
    print("Aucune divergence sur les champs fournis par le runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
