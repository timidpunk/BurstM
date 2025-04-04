# BurstM: Deep Burst Multi-scale SR using Fourier Space with Optical Flow (ECCV 2024)

[EungGu Kang](https://github.com/Egkang-Luis/BurstM), [Byeonghun Lee](https://github.com/ByeonghunLee12), [Sunghoon Im](https://sunghoonim.github.io/), [Kyong Hwan Jin](https://ipa.korea.ac.kr)

This repository contains the official implementation for BurstM introduced in the following paper:

[![Arxiv paper](https://img.shields.io/badge/arXiv-Paper-<COLOR>.svg)](https://arxiv.org/pdf/2409.15384)
[![ECCV paper](https://img.shields.io/badge/ECCV-Paper-<COLOR>.svg)](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/05913.pdf)
[![ECCV Page](https://img.shields.io/badge/ECCV-Page-<COLOR>.svg)](https://eccv2024.ecva.net/virtual/2024/poster/2171)

#### News
- **July 01, 2024:** Paper accepted at ECCV 2024 :tada:
- **Sep 30, 2024:** Paper link updated :tada:

<hr />

> *Multiframesuper-resolution(MFSR)achieveshigherperfor- mance than single image super-resolution (SISR), because MFSR leverages abundant information from multiple frames. Recent MFSR approaches adapt the deformable convolution network (DCN) to align the frames. However, the existing MFSR suffers from misalignments between the reference and source frames due to the limitations of DCN, such as small receptive fields and the predefined number of kernels. From these problems, existing MFSR approaches struggle to represent high-frequency information. To this end, we propose Deep Burst Multi-scale SR using Fourier Space with Optical Flow (BurstM). The proposed method estimates the optical flow offset for accurate alignment and predicts the continuous Fourier coefficient of each frame for representing high-frequency textures. In addition, we have enhanced the network’s flexibility by supporting various super-resolution (SR) scale factors with the unimodel. We demonstrate that our method has the highest performance and flexibility than the existing MFSR methods.*
<hr />

## Overall architectures for BurstM
![BurstM_overall_architecture.png](figs/BurstM_overall_architecture.png)


## Quantitative comparison
![BurstM_quantitative_comparison.png](figs/BurstM_quantitative_comparison.png)

## x4 inference result for BurstSR dataset(Real-world dataset)
![BurstM_BurstSR_x4_result.png](figs/BurstM_BurstSR_x4_result.png)

## Multi-scale inference result for BurstSR dataset(Real-world dataset)
![BurstM_BurstSR_multiscale.png](figs/BurstM_BurstSR_multiscale.png)

## Dependencies
- OS: Ubuntu 22.04
- nvidia cuda: 12.4
- Python: 3.10.14
- pytorch: 2.3.0

We used NVIDIA RTX 3090 24GB, sm86

We recommend using [conda](https://www.anaconda.com/distribution/) for installation:
```
conda env create --file environment.yaml
conda activate BurstM
```

## Training

### SyntheticBurst
1. Download dataset(Zurich RAW to RGB dataset) [Download](http://people.ee.ethz.ch/~ihnatova/pynet.html#dataset).

2. Train

```python3
# Please modify the path of input directory
CUDA_VISIBLE_DEVICES=0,1,2,3 python BurstM_Track_1_training.py --input_dir=<Input DIR> --log_dir=<Log DIR> --model_dir=<Model save DIR> --result_dir=<tensorboard dir>
```

### BurstSR(Real-world data)
1. Download dataset(BurstSR for real-world datasets) [Download](https://github.com/goutamgmb/NTIRE21_BURSTSR/blob/master/burstsr_links.md)

2. Train

```python3
# Please modify the path of input directory
CUDA_VISIBLE_DEVICES=0,1,2,3 python BurstM_Track_2_training.py --input_dir=<Input DIR> --pre_trained=<Pretrained model of SyntheticBurst> --log_dir=<Log DIR> --model_dir=<Model save DIR> --result_dir=<tensorboard dir>
```

## Test

### SyntheticBurst
1. Download pre-trained models of SyntheticBurst [Download](https://drive.google.com/file/d/1XzBOV_F2un0nBWBdCCQCmDzvXlmee-cO/view?usp=sharing).

2. Test

  If you want to change the super-resolution scale, please change --scale.
  Not only intager scales, but also floating scales are possible.
  But the qualities of floating sclae such as x2.5 and x3.5 are not guaranteed.
```python3
# Please modify the path of iamge directory for inputs and pre-trained models(weights).
CUDA_VISIBLE_DEVICES=0 python BurstM_Track_1_evaluation.py --input_dir=<Input DIR> --scale=4 --weights=<Pretrained model of SyntheticBurst> --result_dir=<Result DIR> --result_gt_dir=<GT Result DIR>
```

### BurstSR(Real-world data)
1. Download pre-trained models of BurstSR [Download](https://drive.google.com/file/d/1id83q_IOF7qawO5_4WJ4ZGOFvxkcwbFw/view?usp=sharing)

2. Test

  If you want to change the super-resolution scale, please change --scale.
  Not only intager scales, but also floating scales are possible.
  But the qualities of floating sclae such as x2.5 and x3.5 are not guaranteed.
```python3
# Please modify the path of iamge directory for inputs and pre-trained models(weights).
CUDA_VISIBLE_DEVICES=0 python BurstM_Track_2_evaluation.py --input_dir=<Input DIR> --scale=4 --weights=<Pretrained model of BurstSR> --result_dir=<Result DIR> --result_gt_dir=<GT Result DIR>
``` 

## Citations
If our code helps your research or work, please consider citing our paper.
The following is a BibTeX reference.

```
Will be updated
```

## Acknowledgement
This work is mainly based on [NIS](https://github.com/minshu-kim/Neural-Image-Stitching) and [Burstormer](https://github.com/akshaydudhane16/Burstormer), we thank the authors for the contribution.

