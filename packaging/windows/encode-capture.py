"""Encode real Unity frames, preserving their recorded simulated timing."""
import argparse
import json
from pathlib import Path
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('capture', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
record = json.loads((args.capture/'frames.json').read_text())
paths = sorted(args.capture.glob('*.png'))
times = record['simulated_seconds']
if len(paths) != len(times) or len(paths) < 2:
    raise SystemExit('Missing frames or simulated timestamps')
durations = [max(10, round((b-a)*1000)) for a, b in zip(times, times[1:])]
durations.append(durations[-1])
frames = []
for path in paths:
    with Image.open(path) as frame:
        frames.append(frame.convert('RGB').resize((960, 540)).quantize(colors=128))
args.output.parent.mkdir(parents=True, exist_ok=True)
frames[0].save(args.output, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2)
record.update(frames=len(paths), size=[960, 540], note='Real frozen-policy test; not evidence of successful swing-up',
              checkpoint_step=4196, evaluation_successes=0, evaluation_trials=20)
args.output.with_suffix('.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(args.output)
