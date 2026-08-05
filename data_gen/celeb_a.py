# https://github.com/DeokyunKim/Progressive-Face-Super-Resolution/blob/master/dataloader.py
import os
import random
import traceback

from tqdm import tqdm

from utils.hparams import hparams, set_hparams
from utils.indexed_datasets import IndexedDatasetBuilder
from PIL import Image
from numpy import asarray


def subsample(img_list, max_imgs, seed):
    if max_imgs is None or max_imgs < 0 or max_imgs >= len(img_list):
        return img_list
    rng = random.Random(seed)
    return rng.sample(img_list, max_imgs)


def read_partition(path):
    """Parse a CelebA eval-partition listing into (name, split) pairs.

    Supports both distributions in the wild: the original space-separated
    `list_eval_partition.txt` and the Kaggle CSV `list_eval_partition.csv`
    (comma-separated, with an `image_id,partition` header row).
    """
    is_csv = os.path.splitext(path)[1].lower() == '.csv'
    with open(path, mode='r') as f:
        for i, line in enumerate(f):
            fields = line.strip().split(',' if is_csv else None)
            if len(fields) < 2:
                continue
            if is_csv and i == 0 and not fields[1].strip().isdigit():
                continue  # header row
            yield fields[0].strip(), fields[1].strip()


def build_bin_dataset(imgs, prefix):
    binary_data_dir = hparams['binary_data_dir']
    img_dir = hparams['celeba_img_dir']
    os.makedirs(binary_data_dir, exist_ok=True)
    builder = IndexedDatasetBuilder(f'{binary_data_dir}/{prefix}')
    for img in tqdm(imgs):
        try:
            full_path = f'{img_dir}/{img}'
            image = Image.open(full_path).convert('RGB')
            data = asarray(image)
            builder.add_item({'item_name': img, 'path': full_path, 'img': data})
        except KeyboardInterrupt:
            raise
        except:
            traceback.print_exc()
            print("| binarize img error: ", img)
    builder.finalize()


if __name__ == '__main__':
    set_hparams()
    binary_data_dir = hparams['binary_data_dir']
    eval_partition_path = hparams['celeba_partition_file']
    assert os.path.exists(eval_partition_path), \
        f'partition file not found: {eval_partition_path} (set celeba_partition_file)'
    assert os.path.isdir(hparams['celeba_img_dir']), \
        f'image dir not found: {hparams["celeba_img_dir"]} (set celeba_img_dir)'

    train_img_list = []
    val_img_list = []
    test_img_list = []
    for name, split in read_partition(eval_partition_path):
        if split == '0':
            train_img_list.append(name)
        elif split == '1':
            val_img_list.append(name)
        else:
            test_img_list.append(name)
    print(f'| partition: {len(train_img_list)} train, '
          f'{len(val_img_list)} valid, {len(test_img_list)} test')

    # config_base.yaml's 'seed' default isn't in scope when this script is invoked
    # with a bare celeb_a*.yaml config (no diffsr_base.yaml in the chain).
    seed = hparams.get('seed', 1234)
    train_img_list = subsample(train_img_list, hparams['max_train_imgs'], seed)
    val_img_list = subsample(val_img_list, hparams['max_valid_imgs'], seed)
    test_img_list = subsample(test_img_list, hparams['max_test_imgs'], seed)

    build_bin_dataset(train_img_list, 'train')
    build_bin_dataset(val_img_list, 'valid')
    build_bin_dataset(test_img_list, 'test')
