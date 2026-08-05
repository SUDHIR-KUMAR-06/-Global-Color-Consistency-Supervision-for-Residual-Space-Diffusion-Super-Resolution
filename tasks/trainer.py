import importlib
import os
import random
import subprocess

import torch
from PIL import Image
from tqdm import tqdm
from torch.utils.tensorboard import SummaryWriter
from utils.hparams import hparams, set_hparams
import numpy as np
from utils.utils import plot_img, move_to_cuda, load_checkpoint, save_checkpoint, tensors_to_scalars, load_ckpt, Measure


class Trainer:
    def __init__(self):
        self.logger = self.build_tensorboard(save_dir=hparams['work_dir'], name='tb_logs')
        self.measure = Measure()
        self.dataset_cls = None
        self.metric_keys = ['psnr', 'ssim', 'lpips', 'lr_psnr', 'color_error']
        self.work_dir = hparams['work_dir']
        self.first_val = True
        self.amp = hparams['amp']
        self.amp_scaler = torch.cuda.amp.GradScaler(enabled=self.amp)

        # --- early stopping state ---
        self.es_enabled = hparams['early_stop']
        self.es_key = hparams['early_stop_key']
        self.es_mode = hparams['early_stop_mode']
        assert self.es_mode in ('min', 'max'), f'early_stop_mode must be min|max, got {self.es_mode}'
        self.es_patience = hparams['early_stop_patience']
        self.es_min_delta = hparams['early_stop_min_delta']
        self.es_best = float('inf') if self.es_mode == 'min' else float('-inf')
        self.es_best_step = 0
        self.es_num_bad_evals = 0
        self.should_stop = False

        # --- numerical-stability state ---
        self.skipped_steps = 0

    def is_improvement(self, value):
        """True if `value` beats the best-so-far by more than min_delta."""
        if self.es_mode == 'min':
            return value < self.es_best - self.es_min_delta
        return value > self.es_best + self.es_min_delta

    def check_early_stop(self, metrics, training_step):
        """Update early-stopping state from a validation result.

        Returns True when training should stop. A non-finite monitored value is
        treated as a failed evaluation (never as an improvement) so a diverged
        run cannot latch itself in as 'best'.
        """
        if not self.es_enabled:
            return False
        if self.es_key not in metrics:
            print(f'| early stopping: key {self.es_key!r} not in val metrics '
                  f'{sorted(metrics)}; skipping check')
            return False
        value = float(metrics[self.es_key])
        if not np.isfinite(value):
            self.es_num_bad_evals += 1
            print(f'| early stopping: non-finite {self.es_key}={value}, '
                  f'{self.es_num_bad_evals}/{self.es_patience} bad evals')
        elif self.is_improvement(value):
            self.es_best = value
            self.es_best_step = training_step
            self.es_num_bad_evals = 0
            print(f'| early stopping: new best {self.es_key}={value:.6f} @ step {training_step}')
        else:
            self.es_num_bad_evals += 1
            print(f'| early stopping: no improvement in {self.es_key} '
                  f'({value:.6f} vs best {self.es_best:.6f} @ step {self.es_best_step}), '
                  f'{self.es_num_bad_evals}/{self.es_patience}')
        self.log_metrics({f'val/{self.es_key}_best': self.es_best}, training_step)
        if self.es_num_bad_evals >= self.es_patience:
            print(f'| EARLY STOP at step {training_step}: no improvement in {self.es_key} '
                  f'for {self.es_patience} consecutive validations. '
                  f'Best {self.es_key}={self.es_best:.6f} @ step {self.es_best_step}.')
            return True
        return False

    def build_tensorboard(self, save_dir, name, **kwargs):
        log_dir = os.path.join(save_dir, name)
        os.makedirs(log_dir, exist_ok=True)
        return SummaryWriter(log_dir=log_dir, **kwargs)

    def build_train_dataloader(self):
        dataset = self.dataset_cls('train')
        return torch.utils.data.DataLoader(
            dataset, batch_size=hparams['batch_size'], shuffle=True,
            pin_memory=False, num_workers=hparams['num_workers'])

    def build_val_dataloader(self):
        return torch.utils.data.DataLoader(
            self.dataset_cls('valid'), batch_size=hparams['eval_batch_size'], shuffle=False, pin_memory=False)

    def build_test_dataloader(self):
        return torch.utils.data.DataLoader(
            self.dataset_cls('test'), batch_size=hparams['eval_batch_size'], shuffle=False, pin_memory=False)

    def build_model(self):
        raise NotImplementedError

    def sample_and_test(self, sample):
        raise NotImplementedError

    def build_optimizer(self, model):
        raise NotImplementedError

    def build_scheduler(self, optimizer):
        raise NotImplementedError

    def training_step(self, batch):
        raise NotImplementedError

    def train(self):
        model = self.build_model()
        optimizer = self.build_optimizer(model)
        self.global_step = training_step = load_checkpoint(model, optimizer, hparams['work_dir'])
        self.scheduler = scheduler = self.build_scheduler(optimizer)
        scheduler.step(training_step)
        dataloader = self.build_train_dataloader()

        train_pbar = tqdm(dataloader, initial=training_step, total=float('inf'),
                          dynamic_ncols=True, unit='step')
        while self.global_step < hparams['max_updates'] and not self.should_stop:
            for batch in train_pbar:
                if training_step % hparams['val_check_interval'] == 0:
                    with torch.no_grad():
                        model.eval()
                        metrics = self.validate(training_step)
                    save_checkpoint(model, optimizer, self.work_dir, training_step, hparams['num_ckpt_keep'])
                    # sanity val runs on a partial set, so don't judge it
                    if metrics is not None and training_step > 0:
                        self.should_stop = self.check_early_stop(metrics, training_step)
                        if self.should_stop:
                            break
                model.train()
                batch = move_to_cuda(batch)
                optimizer.zero_grad()
                with torch.cuda.amp.autocast(enabled=self.amp):
                    losses, total_loss = self.training_step(batch)

                # Guard 1: a non-finite loss would poison every weight via
                # backward(), so drop the step before it can.
                if not torch.isfinite(total_loss):
                    self.skipped_steps += 1
                    print(f'| WARNING step {training_step}: non-finite loss '
                          f'({total_loss.item()}), skipping step '
                          f'(total skipped: {self.skipped_steps})')
                    self.log_metrics({'tr/skipped_steps': self.skipped_steps}, training_step)
                    optimizer.zero_grad(set_to_none=True)
                    training_step += 1
                    self.global_step = training_step
                    continue

                self.amp_scaler.scale(total_loss).backward()

                # Gradient clipping must see true (unscaled) gradients, so unscale
                # first; GradScaler.step then knows not to unscale twice.
                grad_norm = None
                if hparams['clip_grad_norm'] > 0:
                    self.amp_scaler.unscale_(optimizer)
                    grad_norm = torch.nn.utils.clip_grad_norm_(
                        [p for g in optimizer.param_groups for p in g['params']],
                        hparams['clip_grad_norm'])

                    # Guard 2: clip_grad_norm_ returns non-finite when any grad
                    # overflowed. Under AMP the scaler already skips such steps,
                    # but without AMP nothing else would.
                    if not torch.isfinite(grad_norm):
                        self.skipped_steps += 1
                        print(f'| WARNING step {training_step}: non-finite grad norm '
                              f'({grad_norm.item()}), skipping step '
                              f'(total skipped: {self.skipped_steps})')
                        self.log_metrics({'tr/skipped_steps': self.skipped_steps}, training_step)
                        optimizer.zero_grad(set_to_none=True)
                        self.amp_scaler.update()
                        training_step += 1
                        self.global_step = training_step
                        continue

                self.amp_scaler.step(optimizer)
                self.amp_scaler.update()
                training_step += 1
                scheduler.step(training_step)
                self.global_step = training_step
                if training_step % 100 == 0:
                    log = {f'tr/{k}': v for k, v in losses.items()}
                    if grad_norm is not None:
                        log['tr/grad_norm'] = grad_norm
                    if self.amp:
                        # a collapsing scale means persistent overflow upstream
                        log['tr/amp_scale'] = self.amp_scaler.get_scale()
                    self.log_metrics(log, training_step)
                train_pbar.set_postfix(**tensors_to_scalars(losses))
                if self.global_step >= hparams['max_updates']:
                    break

        if self.skipped_steps:
            print(f'| training finished with {self.skipped_steps} skipped '
                  f'(non-finite) steps out of {training_step}')

    def validate(self, training_step):
        val_dataloader = self.build_val_dataloader()
        pbar = tqdm(enumerate(val_dataloader), total=len(val_dataloader))
        # sample_and_test returns per-batch *sums* plus an 'n_samples' count, so
        # accumulate across the whole val set and divide once at the end.
        totals = {k: 0. for k in self.metric_keys}
        n_total = 0
        for batch_idx, batch in pbar:
            if self.first_val and batch_idx > hparams['num_sanity_val_steps']:  # 每次运行的第一次validation只跑一小部分数据，来验证代码能否跑通
                break
            batch = move_to_cuda(batch)
            img, rrdb_out, ret = self.sample_and_test(batch)
            img_hr = batch['img_hr']
            img_lr = batch['img_lr']
            img_lr_up = batch['img_lr_up']
            if img is not None:
                self.logger.add_image(f'Pred_{batch_idx}', plot_img(img[0]), self.global_step)
                if hparams.get('aux_l1_loss'):
                    self.logger.add_image(f'rrdb_out_{batch_idx}', plot_img(rrdb_out[0]), self.global_step)
                if self.global_step <= hparams['val_check_interval']:
                    self.logger.add_image(f'HR_{batch_idx}', plot_img(img_hr[0]), self.global_step)
                    self.logger.add_image(f'LR_{batch_idx}', plot_img(img_lr[0]), self.global_step)
                    self.logger.add_image(f'BL_{batch_idx}', plot_img(img_lr_up[0]), self.global_step)
            for k in self.metric_keys:
                totals[k] += ret[k]
            n_total += ret['n_samples']
            pbar.set_postfix(**tensors_to_scalars(
                {k: v / max(n_total, 1) for k, v in totals.items()}))
        metrics = {k: v / max(n_total, 1) for k, v in totals.items()}
        if hparams['infer']:
            print('Val results:', metrics)
        else:
            if not self.first_val:
                self.log_metrics({f'val/{k}': v for k, v in metrics.items()}, training_step)
                print('Val results:', metrics)
            else:
                print('Sanity val results:', metrics)
        self.first_val = False
        return metrics

    def test(self):
        model = self.build_model()
        optimizer = self.build_optimizer(model)
        load_checkpoint(model, optimizer, hparams['work_dir'])
        optimizer = None

        self.results = {k: 0 for k in self.metric_keys}
        self.n_samples = 0
        self.gen_dir = f"{hparams['work_dir']}/results_{self.global_step}_{hparams['gen_dir_name']}"
        if hparams['test_save_png']:
            subprocess.check_call(f'rm -rf {self.gen_dir}', shell=True)
            os.makedirs(f'{self.gen_dir}/outputs', exist_ok=True)
            os.makedirs(f'{self.gen_dir}/SR', exist_ok=True)

        self.model.sample_tqdm = False
        torch.backends.cudnn.benchmark = False
        if hparams['test_save_png']:
            if hasattr(self.model.denoise_fn, 'make_generation_fast_'):
                self.model.denoise_fn.make_generation_fast_()
            os.makedirs(f'{self.gen_dir}/RRDB', exist_ok=True)
            os.makedirs(f'{self.gen_dir}/HR', exist_ok=True)
            os.makedirs(f'{self.gen_dir}/LR', exist_ok=True)
            os.makedirs(f'{self.gen_dir}/UP', exist_ok=True)

        with torch.no_grad():
            model.eval()
            test_dataloader = self.build_test_dataloader()
            pbar = tqdm(enumerate(test_dataloader), total=len(test_dataloader))
            for batch_idx, batch in pbar:
                move_to_cuda(batch)
                gen_dir = self.gen_dir
                item_names = batch['item_name']
                img_hr = batch['img_hr']
                img_lr = batch['img_lr']
                img_lr_up = batch['img_lr_up']

                if hparams['save_intermediate']:
                    item_name = item_names[0]
                    img, rrdb_out, imgs = self.model.sample(
                        img_lr, img_lr_up, img_hr.shape, save_intermediate=True)
                    os.makedirs(f"{gen_dir}/intermediate/{item_name}", exist_ok=True)
                    Image.fromarray(self.tensor2img(img_hr)[0]).save(f"{gen_dir}/intermediate/{item_name}/G.png")

                    for i, (m, x_recon) in enumerate(tqdm(imgs)):
                        if i % (hparams['timesteps'] // 20) == 0 or i == hparams['timesteps'] - 1:
                            t_batched = torch.stack([torch.tensor(i).to(img.device)] * img.shape[0])
                            x_t = self.model.q_sample(self.model.img2res(img_hr, img_lr_up), t=t_batched)
                            Image.fromarray(self.tensor2img(x_t)[0]).save(
                                f"{gen_dir}/intermediate/{item_name}/noise1_{i:03d}.png")
                            Image.fromarray(self.tensor2img(m)[0]).save(
                                f"{gen_dir}/intermediate/{item_name}/noise_{i:03d}.png")
                            Image.fromarray(self.tensor2img(x_recon)[0]).save(
                                f"{gen_dir}/intermediate/{item_name}/{i:03d}.png")
                    return {}

                res = self.sample_and_test(batch)
                if len(res) == 3:
                    img_sr, rrdb_out, ret = res
                else:
                    img_sr, ret = res
                    rrdb_out = img_sr
                img_hr = batch['img_hr']
                img_lr = batch['img_lr']
                img_lr_up = batch.get('img_lr_up', img_lr_up)
                if img_sr is not None:
                    metrics = list(self.metric_keys)
                    for k in metrics:
                        self.results[k] += ret[k]
                    self.n_samples += ret['n_samples']
                    print({k: round(self.results[k] / self.n_samples, 3) for k in metrics}, 'total:', self.n_samples)
                    if hparams['test_save_png'] and img_sr is not None:
                        img_sr = self.tensor2img(img_sr)
                        img_hr = self.tensor2img(img_hr)
                        img_lr = self.tensor2img(img_lr)
                        img_lr_up = self.tensor2img(img_lr_up)
                        rrdb_out = self.tensor2img(rrdb_out)
                        for item_name, hr_p, hr_g, lr, lr_up, rrdb_o in zip(
                                item_names, img_sr, img_hr, img_lr, img_lr_up, rrdb_out):
                            item_name = os.path.splitext(item_name)[0]
                            hr_p = Image.fromarray(hr_p)
                            hr_g = Image.fromarray(hr_g)
                            lr = Image.fromarray(lr)
                            lr_up = Image.fromarray(lr_up)
                            rrdb_o = Image.fromarray(rrdb_o)
                            hr_p.save(f"{gen_dir}/outputs/{item_name}[SR].png")
                            hr_g.save(f"{gen_dir}/outputs/{item_name}[HR].png")
                            lr.save(f"{gen_dir}/outputs/{item_name}[LR].png")
                            hr_p.save(f"{gen_dir}/SR/{item_name}.png")
                            hr_g.save(f"{gen_dir}/HR/{item_name}.png")
                            lr.save(f"{gen_dir}/LR/{item_name}.png")
                            lr_up.save(f"{gen_dir}/UP/{item_name}.png")
                            rrdb_o.save(f"{gen_dir}/RRDB/{item_name}.png")

    # utils
    def log_metrics(self, metrics, step):
        metrics = self.metrics_to_scalars(metrics)
        logger = self.logger
        for k, v in metrics.items():
            if isinstance(v, torch.Tensor):
                v = v.item()
            logger.add_scalar(k, v, step)

    def metrics_to_scalars(self, metrics):
        new_metrics = {}
        for k, v in metrics.items():
            if isinstance(v, torch.Tensor):
                v = v.item()

            if type(v) is dict:
                v = self.metrics_to_scalars(v)

            new_metrics[k] = v

        return new_metrics

    @staticmethod
    def tensor2img(img):
        img = np.round((img.permute(0, 2, 3, 1).cpu().numpy() + 1) * 127.5)
        img = img.clip(min=0, max=255).astype(np.uint8)
        return img


if __name__ == '__main__':
    set_hparams()

    random.seed(hparams['seed'])
    np.random.seed(hparams['seed'])
    torch.manual_seed(hparams['seed'])
    torch.cuda.manual_seed_all(hparams['seed'])

    pkg = ".".join(hparams["trainer_cls"].split(".")[:-1])
    cls_name = hparams["trainer_cls"].split(".")[-1]
    trainer = getattr(importlib.import_module(pkg), cls_name)()
    if not hparams['infer']:
        trainer.train()
    else:
        trainer.test()
