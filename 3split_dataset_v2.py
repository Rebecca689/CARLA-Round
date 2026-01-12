# scripts/split_dataset.py
"""
划分数据集为训练集、验证集、测试集
- 训练集: 70%
- 验证集: 15%
- 测试集: 15%
"""
import sys

sys.path.append('D:/Carla Simulation')

import pandas as pd
import numpy as np
from pathlib import Path
from roundabout_config_v2 import *


def split_by_trajectory(df, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15):
    """按轨迹划分数据集（确保同一轨迹在同一集合）"""

    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "比例之和必须为1"

    # 获取所有唯一的轨迹ID
    unique_tracks = df['trackId'].unique()
    n_tracks = len(unique_tracks)

    print(f"\n总轨迹数: {n_tracks}")

    # 随机打乱轨迹顺序
    np.random.seed(42)  # 固定随机种子，确保可复现
    shuffled_tracks = np.random.permutation(unique_tracks)

    # 计算划分点
    train_end = int(n_tracks * train_ratio)
    val_end = train_end + int(n_tracks * val_ratio)

    # 划分轨迹ID
    train_tracks = shuffled_tracks[:train_end]
    val_tracks = shuffled_tracks[train_end:val_end]
    test_tracks = shuffled_tracks[val_end:]

    # 根据轨迹ID划分数据
    train_df = df[df['trackId'].isin(train_tracks)]
    val_df = df[df['trackId'].isin(val_tracks)]
    test_df = df[df['trackId'].isin(test_tracks)]

    print(f"\n划分结果:")
    print(f"  训练集: {len(train_tracks)} 条轨迹 ({len(train_tracks) / n_tracks * 100:.1f}%)")
    print(f"  验证集: {len(val_tracks)} 条轨迹 ({len(val_tracks) / n_tracks * 100:.1f}%)")
    print(f"  测试集: {len(test_tracks)} 条轨迹 ({len(test_tracks) / n_tracks * 100:.1f}%)")

    return train_df, val_df, test_df


def analyze_split(train_df, val_df, test_df):
    """分析划分后的数据分布"""

    print("\n" + "=" * 60)
    print("数据集统计")
    print("=" * 60)

    datasets = {
        '训练集': train_df,
        '验证集': val_df,
        '测试集': test_df
    }

    for name, df in datasets.items():
        print(f"\n{name}:")
        print(f"  行数: {len(df):,}")
        print(f"  轨迹数: {df['trackId'].nunique()}")
        print(f"  场景数: {df['scenario_id'].nunique()}")
        print(f"  平均速度: {df['speed'].mean():.2f} m/s")
        print(f"  平均半径: {df['radius'].mean():.2f} m")

        # 场景分布
        print(f"  天气分布:")
        for weather in df['weather'].unique():
            count = (df['weather'] == weather).sum()
            print(f"    {weather}: {count:,} ({count / len(df) * 100:.1f}%)")


def main():
    print("=" * 60)
    print("数据集划分")
    print("=" * 60)

    # 读取清洗后的数据
    input_file = Path(PROCESSED_DATA_DIR) / 'carla_round_all.csv'

    if not input_file.exists():
        print(f"❌ 文件不存在: {input_file}")
        print("请先运行 clean_and_merge.py")
        return

    print(f"\n读取数据: {input_file}")
    df = pd.read_csv(input_file)
    print(f"✅ 加载完成: {len(df):,} 行, {df['trackId'].nunique()} 条轨迹")

    # 划分数据集
    train_df, val_df, test_df = split_by_trajectory(df)

    # 分析划分结果
    analyze_split(train_df, val_df, test_df)

    # 保存划分后的数据
    print("\n" + "=" * 60)
    print("保存数据集")
    print("=" * 60)

    files = {
        'train.csv': train_df,
        'val.csv': val_df,
        'test.csv': test_df
    }

    for filename, data in files.items():
        filepath = Path(PROCESSED_DATA_DIR) / filename
        data.to_csv(filepath, index=False)
        size_mb = filepath.stat().st_size / 1024 / 1024
        print(f"  ✓ {filename}: {len(data):,} 行, {size_mb:.1f} MB")

    print("\n" + "=" * 60)
    print("✅ 划分完成！")
    print("=" * 60)
    print(f"\n数据位置: {PROCESSED_DATA_DIR}")
    print("\n文件列表:")
    print("  - carla_round_all.csv (完整数据)")
    print("  - train.csv (训练集)")
    print("  - val.csv (验证集)")
    print("  - test.csv (测试集)")

    print("\n下一步: 运行 visualize_data.py 生成可视化")


if __name__ == '__main__':
    main()