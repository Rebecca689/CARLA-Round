# CARLA-Round

A Multi-Factor Simulation Dataset for Roundabout Trajectory Prediction

[![Paper](https://img.shields.io/badge/Paper-IEEE-blue)](https://github.com/Rebecca689/CARLA-Round)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Overview

CARLA-Round is a systematically designed simulation dataset for roundabout trajectory prediction. Unlike randomly sampled simulation data, this dataset uses a structured **5×5 factorial design** varying:

- **Weather conditions** (5 types): Clear Noon, Wet Noon, Soft Rain, Hard Rain, Clear Sunset
- **Traffic density levels** (5 levels): LOS A-E following HCM 2010 guidelines

This yields **25 controlled scenarios** with **449 trajectories** and **93,803 frames**, enabling precise analysis of how different conditions influence trajectory prediction performance.

## Installation

### Requirements

- Python 3.7+
- CARLA 0.9.15
- Dependencies:

```bash
pip install pandas numpy carla
```

### Setup

1. Clone this repository:
```bash
git clone https://github.com/Rebecca689/CARLA-Round.git
cd CARLA-Round
```

2. Install CARLA 0.9.15 from [CARLA releases](https://github.com/carla-simulator/carla/releases)

3. Update the path in `roundabout_config_v2.py`:
```python
BASE_DIR = 'your/path/to/project'
```

## Usage

### 1. Test Environment (Optional)

```bash
python test_mixed_behavior.py
```

### 2. Collect Data

```bash
python 1collect_full_v2_mixed_behavior.py
```

### 3. Clean and Merge Data

```bash
python 2clean_and_merge_v2.py
```

### 4. Split Dataset

```bash
python 3split_dataset_v2.py
```

## Configuration

### Weather Types

| Weather | Speed Adjustment | Coverage |
|---------|-----------------|----------|
| Clear Noon | 0% | 52.1% |
| Wet Noon | +8% | 18.7% |
| Soft Rain | +12% | 14.2% |
| Hard Rain | +20% | 6.8% |
| Clear Sunset | +5% | 2.5% |

### Traffic Density (HCM 2010)

| Level | LOS | Flow (veh/h) | Target (180s) |
|-------|-----|--------------|---------------|
| Very Sparse | A | 300 | 15 |
| Sparse | B | 500 | 25 |
| Medium | C | 1,000 | 50 |
| Dense | D | 1,300 | 65 |
| Very Dense | E | 1,500 | 75 |

### Driving Behaviors

- **Aggressive** (25%): 20% faster speeds
- **Normal** (50%): Baseline speeds
- **Cautious** (25%): 30% slower speeds

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total trajectories | 449 |
| Total frames | 93,803 |
| Avg. trajectory length | 20.9 s |
| Position accuracy | <0.01 m |
| Train/Val/Test split | 314/67/68 |

### Baseline Performance

| Method | ADE (m) | FDE (m) |
|--------|---------|---------|
| LSTM | 0.512 | 0.896 |
| GCN-only | 0.438 | 0.784 |
| GRU+GCN | 0.345 | 0.615 


## Citation

If you use this dataset in your research, please cite:


## Related Work

- [rounD Dataset](https://www.round-dataset.com/) - Real-world roundabout trajectory dataset
- [CARLA Simulator](https://carla.org/) - Open-source autonomous driving simulator


## Contact

- Xiaotong Zhou - xiaotong.zhou@warwick.ac.uk
- School of Engineering, University of Warwick, UK
