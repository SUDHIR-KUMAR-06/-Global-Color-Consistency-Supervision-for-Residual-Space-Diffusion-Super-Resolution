import os

os.environ["OMP_NUM_THREADS"] = "1"

from multiprocessing import Pool
import glob
import os
from os import path as osp
from PIL import Image
from numpy import asarray
from tqdm import tqdm

from utils.hparams import hparams, set_hparams
from utils.indexed_datasets import IndexedDatasetBuilder
from utils.matlab_resize import imresize


def worker(args):
    i, path, patch_size, crop_size, thresh_size, sr_scale = args
    img_name, extension = osp.splitext(osp.basename(path))
    img = Image.open(path).convert('RGB')
    img = asarray(img)
    h, w, c = img.shape
    h = h - h % sr_scale
    w = w - w % sr_scale
    img = img[:h, :w]
    h, w, c = img.shape
    img_lr = imresize(img, 1 / sr_scale)
    ret = []
    x = 0
    while x < h - thresh_size:
        y = 0
        while y < w - thresh_size:
            x_l_left = x // sr_scale
            x_l_right = (x + crop_size[0]) // sr_scale
            y_l_left = y // sr_scale
            y_l_right = (y + crop_size[1]) // sr_scale
            cropped_img = img[x:x + crop_size[0], y:y + crop_size[1], ...]
            cropped_img_lr = img_lr[x_l_left:x_l_right, y_l_left:y_l_right]
            # Tiles at the right/bottom edge get clipped short by the slicing
            # above. Test and valid items are consumed whole, so ragged tiles
            # cannot be collated into a batch; drop them and keep only complete
            # ones. (Upstream never hit this because it stored just the first
            # tile of each test image, which is always full size.)
            if cropped_img.shape[0] != crop_size[0] or cropped_img.shape[1] != crop_size[1]:
                y += crop_size[1]
                continue
            ret.append({
                # Tiles must not share a name: test-time PNGs are written as
                # <item_name>.png, so a shared name makes every tile of an image
                # overwrite the previous one, collapsing a 2000-tile test set to
                # ~60 files and computing FID over those instead.
                'item_name': f'{img_name}_{x // crop_size[0]:02d}_{y // crop_size[1]:02d}',
                'loc': [x // crop_size[0], y // crop_size[1]],
                'loc_bdr': [(h + crop_size[0] - 1) // crop_size[0], (w + crop_size[1] - 1) // crop_size[1]],
                'path': path, 'img': cropped_img,
                'img_lr': cropped_img_lr,
            })
            y += crop_size[1]
        x += crop_size[0]

    return i, ret


def build_bin_dataset(paths, binary_data_dir, prefix, patch_size, crop_size, thresh_size):
    if isinstance(crop_size, int):
        crop_size = [crop_size, crop_size]
    sr_scale = hparams['sr_scale']
    assert crop_size[0] % sr_scale == 0
    assert crop_size[1] % sr_scale == 0
    assert patch_size % sr_scale == 0
    assert thresh_size % sr_scale == 0

    builder = IndexedDatasetBuilder(f'{binary_data_dir}/{prefix}')

    def get_worker_args():
        for i, path in enumerate(paths):
            yield i, path, patch_size, crop_size, thresh_size, sr_scale

    # Keeping only the first tile of each test image (upstream behaviour) leaves
    # too few test samples for a meaningful FID once the split is small, so allow
    # storing every tile instead.
    test_all_tiles = hparams['df2k_test_all_tiles']
    n_items = 0
    with Pool(processes=hparams['df2k_num_workers']) as pool:
        for ret in tqdm(pool.imap_unordered(worker, list(get_worker_args())), total=len(paths)):
            if prefix == 'test' and not test_all_tiles:
                builder.add_item(ret[1][0], id=ret[0])
                n_items += 1
            else:
                for r in ret[1]:
                    builder.add_item(r)
                    n_items += 1
    builder.finalize()
    print(f'| built {prefix}: {n_items} items from {len(paths)} images')


if __name__ == '__main__':
    set_hparams()
    binary_data_dir = hparams['binary_data_dir']
    os.makedirs(binary_data_dir, exist_ok=True)
    train_img_list = []
    for pattern in hparams['df2k_train_globs']:
        train_img_list += sorted(glob.glob(pattern))
    assert train_img_list, \
        f'no training images matched {hparams["df2k_train_globs"]} (set df2k_train_globs)'

    test_img_list = []
    for pattern in hparams['df2k_test_globs']:
        test_img_list += sorted(glob.glob(pattern))
    if not test_img_list:
        # DIV2K's official validation set is distributed separately; when only the
        # train split is available, hold out a deterministic tail of it so train
        # and test never overlap.
        n_holdout = hparams['df2k_holdout_test']
        assert len(train_img_list) > n_holdout, \
            f'need more than {n_holdout} training images to hold out a test set'
        train_img_list, test_img_list = train_img_list[:-n_holdout], train_img_list[-n_holdout:]
        print(f'| no test globs matched; held out the last {n_holdout} training images as test')

    n_train = hparams['df2k_max_train_imgs']
    if 0 <= n_train < len(train_img_list):
        train_img_list = train_img_list[:n_train]
    print(f'| df2k: {len(train_img_list)} train images, {len(test_img_list)} test images')

    crop_size = hparams['crop_size']
    patch_size = hparams['patch_size']
    thresh_size = hparams['thresh_size']
    test_crop_size = hparams['test_crop_size']
    test_thresh_size = hparams['test_thresh_size']
    build_bin_dataset(test_img_list, binary_data_dir, 'test', patch_size, test_crop_size, test_thresh_size)
    build_bin_dataset(train_img_list, binary_data_dir, 'train', patch_size, crop_size, thresh_size)
