"""Evaluate an adapted controller with the same rollouts as the forward sweep.

For a checkpoint from adapt_controller.py, run the weakness it was trained on,
each single group alone, and the healthy model. Each scenario: one
deterministic start plus seeds with the training reset noise (0.001).
Outcomes use the sweep's classes (walked / deviated / fell).

  python scripts/evaluate_adaptation.py --name glut_med_max_020 --step 100000
  python scripts/evaluate_adaptation.py --name glut_med_max_020 --step final
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_weakness_sweep as sweep  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--step', default='final', help="checkpoint step, 'final', or 'original'")
    parser.add_argument('--seeds', type=int, default=5)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    folder = ROOT / 'results/adaptation' / args.name
    config = json.loads((folder / 'config.json').read_text())
    groups, capacity = tuple(config['groups']), config['capacity']
    if args.step == 'original':
        model_path = env_path = None
    elif args.step == 'final':
        model_path, env_path = folder / 'final_model.zip', folder / 'final_env.zip'
    else:
        model_path, env_path = folder / f'model_{args.step}.zip', folder / f'env_{args.step}.zip'
    scenarios = [(groups, capacity)] + [((g,), capacity) for g in groups] + [((), 1.0)]
    jobs = [(s, c, 0, 0.0) for s, c in scenarios] + \
           [(s, c, k, 0.001) for s, c in scenarios for k in range(args.seeds)]
    with ProcessPoolExecutor(args.workers, initializer=sweep.init_worker,
                             initargs=(model_path and str(model_path), env_path and str(env_path))) as pool:
        results = list(pool.map(sweep.rollout, jobs))
    summary = {}
    for r in results:
        key = ('+'.join(g.replace('right_', '') for g in r['groups']) or 'normal') + f" @{r['remaining_active_capacity']:.2f}"
        entry = summary.setdefault(key, {'walked': 0, 'deviated': 0, 'fell': 0, 'max_errors': []})
        entry[r['outcome']] += 1
        entry['max_errors'].append(round(r['max_mean_coordinate_error_rad'], 3))
    report = {'checkpoint': args.step, 'trained_on': {'groups': list(groups), 'capacity': capacity},
              'summary': summary,
              'results': [{k: v for k, v in r.items() if k != 'error_trace'} for r in results]}
    out = folder / f'eval_{args.step}.json'
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for key, e in summary.items():
        print(f"{key:45s} walked {e['walked']}  deviated {e['deviated']}  fell {e['fell']}   max err {e['max_errors']}")


if __name__ == '__main__':
    main()
