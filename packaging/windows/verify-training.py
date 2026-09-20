"""Read-only tensor evidence; run with the private Python, never infer skill from it."""
import argparse
import json
from pathlib import Path

import torch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('experiment', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()

initial_path = args.experiment / 'snapshots' / 'initial.pt'
latest_path = args.experiment / 'snapshots' / 'latest.pt'
if not initial_path.is_file() or not latest_path.is_file():
    raise FileNotFoundError(f'Missing checkpoint snapshot(s): {initial_path} or {latest_path}')

initial = torch.load(initial_path, map_location='cpu', weights_only=True)
latest = torch.load(latest_path, map_location='cpu', weights_only=True)
if 'Policy' not in latest or 'Policy' not in initial:
    raise KeyError('Checkpoint is missing the Policy module')

deltas = {key: float((latest['Policy'][key] - value).abs().max())
          for key, value in initial['Policy'].items()
          if torch.is_floating_point(value) and value.numel()}

events_path = args.experiment / 'events.jsonl'
events = []
if events_path.is_file():
    for line in events_path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
starts = [e['steps'] for e in events if e.get('event') == 'training']
if 'Optimizer:value_optimizer' not in latest:
    raise KeyError('Checkpoint is missing the optimizer state')
optimizer = latest['Optimizer:value_optimizer']
report = dict(schema_version=1, experiment=args.experiment.name,
              changed_policy_tensors=sum(value > 0 for value in deltas.values()),
              maximum_absolute_change=max(deltas.values()),
              initial_step=int(initial['global_step']['_GlobalSteps__global_step']),
              latest_step=int(latest['global_step']['_GlobalSteps__global_step']),
              session_start_steps=starts, checkpoint_modules=list(latest),
              optimizer_parameter_states=len(optimizer['state']),
              optimizer_max_step=max(float(s['step']) for s in optimizer['state'].values()),
              demonstrates='optimization and resume; not swing-up competence')
assert report['changed_policy_tensors'] > 0
assert report['initial_step'] == 0 and len(starts) >= 2 and starts[1] > 0
assert report['latest_step'] > starts[1] and report['optimizer_parameter_states'] > 0
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
