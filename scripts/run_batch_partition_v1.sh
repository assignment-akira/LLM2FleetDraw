#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-all}"
[[ "$MODE" == all || "$MODE" == prepare || "$MODE" == draw ]] || { echo 'Usage: bash scripts/run_batch_partition_v1.sh all|prepare|draw';exit 2; }
OUT=data/results/batch_partition
mkdir -p "$OUT" logs data/sd15_eval/batch_partition/materials
[[ -f compose.sd15.yaml && -f compose.yaml && -s data/plans/logo_one_turtle_full.json ]] || { echo 'MISSING SD15 compose, ROS compose, or robot baseline plan';exit 2; }
if [[ "$MODE" == all || "$MODE" == prepare ]]; then
  mkdir -p "$OUT/plans" "$OUT/materials"
  cp data/plans/logo_one_turtle_full.json "$OUT/plans/robot.json"
  # Existing robot source is pre-verified; do not regenerate it.
  echo 'PHASE 1: generating turtle and flower using existing SD1.5 + Logo.Redmond'
  sudo docker compose -f compose.sd15.yaml run --rm -T sd15 python3 /workspace/batch_partition/generate_subjects.py
  cp data/sd15_eval/batch_partition/materials/{turtle,flower}.{png,json} "$OUT/materials/"
  echo 'PHASE 2: extracting strokes with existing OpenCV pipeline'
  for subj in turtle flower; do
    sudo docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
      --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,noexec,nosuid,size=64m \
      -v "$PWD/contour_compare:/contour_code:ro" \
      -v "$PWD/batch_partition_v1:/batch:ro" \
      -v "$PWD/$OUT/materials:/inputs:ro" \
      -v "$PWD/$OUT/plans:/plans" \
      llm2fleetdraw-contour-compare:v1 \
      python /batch/extract_strokes.py --input "/inputs/$subj.png" --out "/plans/$subj.json" --subject "$subj"
  done
  echo 'PHASE 3: scoring 24 partition configurations'
  python3 batch_partition_v1/partition.py --root "$OUT"
fi
if [[ "$MODE" == all || "$MODE" == draw ]]; then
  [[ -s "$OUT/selected.json" ]] || { echo 'MISSING selected.json; run prepare first';exit 3; }
  sudo docker compose -f compose.yaml exec -T ros2-fleet bash -lc 'source /opt/ros/humble/setup.bash && ros2 node list' | grep -Fx /turtlesim >/dev/null || { echo 'ERROR: turtlesim GUI is not running in WSL1';exit 4; }
  echo 'PHASE 4: draw six top-ranked configurations, one at a time. Each run RESETS canvas.'
  python3 batch_partition_v1/write_jobs.py "$OUT/selected.json" "$OUT/draw_jobs.txt"
  while IFS='|' read -r name robots method plan; do
    echo "DRAW START $name $robots $method"
    sudo docker compose -f compose.yaml exec -T ros2-fleet bash -lc 'source /opt/ros/humble/setup.bash && ros2 service call /reset std_srvs/srv/Empty "{}"' >/dev/null
    log="$OUT/draw_${name}_${robots}_${method}.log"
    # Save each result separately; stop immediately on any controller error.
    sudo docker compose -f compose.yaml exec -T ros2-fleet bash -lc \
      "source /opt/ros/humble/setup.bash && python3 /workspace/one_turtle_logo/batch_partition/launch_generic.py --plan /data/results/batch_partition/partitions/${name}_${robots}_${method}/plan.json" \
      2>&1 | tee "$log"
    echo "DRAW FINISHED $name $robots $method"
  done < "$OUT/draw_jobs.txt"
fi
python3 batch_partition_v1/package.py "$OUT" /mnt/c/Users/udonzin/Downloads/LLM2FleetDraw_batch_partition_results.zip
printf '\nSTATUS: PASS\nRESULT: Windows Downloads/LLM2FleetDraw_batch_partition_results.zip\n'
