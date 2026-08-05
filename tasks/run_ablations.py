"""
CC-ResDiff ablation driver.

Runs the sweeps from the CC-ResDiff experimental plan at a reduced training
budget (see configs/diffsr_celeb_small_ablation.yaml), evaluating each setting
and collecting the metrics into one CSV/JSON table.

Two 1-D sweeps are run, not the full grid:
  * lambda_color in {0.01, 0.1, 0.5, 1.0}  at color_pool_size = 8
  * color_pool_size in {4, 8, 16}          at lambda_color = 0.1
(lambda=0.1, size=8 is shared by both and is only trained once.)

A use_color_loss=false arm is included at the same budget. Without it the sweep
would show how the settings compare to each other but not whether the GCC loss
helps at all at this budget, which is the question the ablation exists to answer.

Usage:
    python tasks/run_ablations.py --rrdb_ckpt checkpoints/rrdb_celebA_small
    python tasks/run_ablations.py --dry_run          # print the plan and exit
"""
import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import time

CONFIG = 'configs/diffsr_celeb_small_ablation.yaml'
LAMBDAS = [0.01, 0.1, 0.5, 1.0]
POOL_SIZES = [4, 8, 16]
DEFAULT_LAMBDA = 0.1
DEFAULT_POOL = 8


def build_plan():
    """Return [(exp_name, hparam_overrides, description)], deduplicated."""
    plan, seen = [], set()

    plan.append(('abl_baseline', {'use_color_loss': 'False'}, 'no GCC loss (reference)'))
    seen.add('abl_baseline')

    for lam in LAMBDAS:
        name = f'abl_lam{lam}_size{DEFAULT_POOL}'
        if name in seen:
            continue
        plan.append((name,
                     {'use_color_loss': 'True', 'lambda_color': lam,
                      'color_pool_size': DEFAULT_POOL},
                     f'lambda_color={lam}'))
        seen.add(name)

    for size in POOL_SIZES:
        name = f'abl_lam{DEFAULT_LAMBDA}_size{size}'
        if name in seen:
            continue
        plan.append((name,
                     {'use_color_loss': 'True', 'lambda_color': DEFAULT_LAMBDA,
                      'color_pool_size': size},
                     f'color_pool_size={size}'))
        seen.add(name)
    return plan


def run(cmd):
    print(f'\n$ {" ".join(cmd)}', flush=True)
    r = subprocess.run(cmd, env={**os.environ, 'PYTHONPATH': '.'})
    return r.returncode


def latest_metrics(exp_name):
    paths = sorted(glob.glob(f'checkpoints/{exp_name}/results_*/metrics.json'))
    if not paths:
        return None
    with open(paths[-1]) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rrdb_ckpt', default='checkpoints/rrdb_celebA_small')
    ap.add_argument('--out', default='checkpoints/ablation_results')
    ap.add_argument('--dry_run', action='store_true')
    ap.add_argument('--skip_existing', action='store_true',
                    help='skip runs that already have metrics.json')
    args = ap.parse_args()

    plan = build_plan()
    print(f'Ablation plan ({len(plan)} runs):')
    for name, hp, desc in plan:
        print(f'  {name:28s}  {desc:24s}  {hp}')
    if args.dry_run:
        return

    os.makedirs(args.out, exist_ok=True)
    rows = []
    for i, (name, hp, desc) in enumerate(plan, 1):
        print(f'\n{"=" * 70}\n[{i}/{len(plan)}] {name}  ({desc})\n{"=" * 70}', flush=True)
        if args.skip_existing and latest_metrics(name):
            print('| already has metrics.json, skipping')
        else:
            overrides = ','.join(f'{k}={v}' for k, v in hp.items())
            hparams = f'rrdb_ckpt={args.rrdb_ckpt},{overrides}'
            t0 = time.time()
            rc = run([sys.executable, '-u', 'tasks/trainer.py', '--config', CONFIG,
                      '--exp_name', name, '--reset', f'--hparams={hparams}'])
            if rc != 0:
                print(f'| TRAINING FAILED for {name} (rc={rc}); skipping its evaluation')
                rows.append({'run': name, 'setting': desc, 'status': f'train_failed_rc{rc}'})
                continue
            print(f'| trained in {(time.time() - t0) / 60:.1f} min', flush=True)

            rc = run([sys.executable, '-u', 'tasks/evaluate.py', '--config', CONFIG,
                      '--exp_name', name, f'--hparams={hparams}'])
            if rc != 0:
                print(f'| EVALUATION FAILED for {name} (rc={rc})')
                rows.append({'run': name, 'setting': desc, 'status': f'eval_failed_rc{rc}'})
                continue

        m = latest_metrics(name)
        if m is None:
            rows.append({'run': name, 'setting': desc, 'status': 'no_metrics'})
            continue
        row = {'run': name, 'setting': desc, 'status': 'ok',
               'lambda_color': hp.get('lambda_color', ''),
               'color_pool_size': hp.get('color_pool_size', ''),
               'use_color_loss': hp.get('use_color_loss')}
        row.update({k: round(float(v), 5) for k, v in m.items()})
        rows.append(row)
        print(f'| {name}: {row}', flush=True)

    # union of keys so a failed run's missing metric columns don't break the writer
    fields, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    csv_path = f'{args.out}/ablations.csv'
    with open(csv_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(f'{args.out}/ablations.json', 'w') as f:
        json.dump(rows, f, indent=2)
    print(f'\nWrote {csv_path} and {args.out}/ablations.json')
    print(f'{len([r for r in rows if r.get("status") == "ok"])}/{len(rows)} runs succeeded')


if __name__ == '__main__':
    main()
