# scripts/2clean_and_merge_v2.py
"""
合并并清洗75个场景的数据
✅ 支持5密度配置
✅ 流量验证
"""
import sys
sys.path.append('D:/Carla Simulation')

import pandas as pd
import numpy as np
from pathlib import Path
from roundabout_config_v2 import *


def load_all_scenarios():
    """加载所有场景数据"""
    print(f"正在加载{TOTAL_SCENARIOS}个场景...")

    all_data = []
    for i in range(TOTAL_SCENARIOS):
        file_path = Path(RAW_DATA_DIR) / f'scenario_{i:03d}.csv'
        if file_path.exists():
            df = pd.read_csv(file_path)
            df['scenario_id'] = i
            all_data.append(df)
            print(f"  ✓ scenario_{i:03d}.csv: {len(df):,} 行, {df['trackId'].nunique()} 轨迹")
        else:
            print(f"  ✗ scenario_{i:03d}.csv: 未找到")

    if not all_data:
        print("❌ 没有找到任何数据文件")
        return None

    merged = pd.concat(all_data, ignore_index=True)
    print(f"\n✅ 加载完成: {len(merged):,} 行")

    return merged


def verify_flow_rates(df):
    """验证流量是否符合目标"""
    print("\n" + "=" * 80)
    print("流量验证 (基于HCM 2010目标)")
    print("=" * 80)
    
    print(f"\n核心区定义: 半径 ≤ 25米")
    print(f"验证标准: 实际通过车辆数 ≈ 目标值 ± 20%")
    
    results = []
    
    for scenario_id in sorted(df['scenario_id'].unique()):
        scenario_data = df[df['scenario_id'] == scenario_id]
        
        density = scenario_data['traffic_density'].iloc[0]
        weather = scenario_data['weather'].iloc[0]
        behavior = scenario_data['behavior_type'].iloc[0]
        
        # 统计核心区轨迹
        core_data = scenario_data[scenario_data['radius'] <= 25]
        core_tracks = core_data['trackId'].nunique()
        
        # 获取目标值
        target = TRAFFIC_DENSITIES[density]['target_passages']
        
        # 计算偏差
        deviation = (core_tracks - target) / target * 100 if target > 0 else 0
        status = "✅" if abs(deviation) <= 20 else "⚠️"
        
        results.append({
            'scenario_id': scenario_id,
            'weather': weather,
            'density': density,
            'behavior': behavior,
            'target': target,
            'actual': core_tracks,
            'deviation': deviation,
            'status': status
        })
    
    results_df = pd.DataFrame(results)
    
    # 打印结果
    print(f"\n{'场景ID':<8} {'密度':<12} {'行为':<12} {'目标':<6} {'实际':<6} {'偏差':<8} {'状态'}")
    print("-" * 80)
    
    for _, row in results_df.iterrows():
        print(f"{row['scenario_id']:>6}   {row['density']:<12} {row['behavior']:<12} "
              f"{row['target']:>4}   {row['actual']:>4}   {row['deviation']:>+6.1f}%  {row['status']}")
    
    # 按密度统计
    print("\n" + "=" * 80)
    print("按密度统计")
    print("=" * 80)
    
    for density in TRAFFIC_DENSITIES.keys():
        density_results = results_df[results_df['density'] == density]
        if len(density_results) == 0:
            continue
            
        target = TRAFFIC_DENSITIES[density]['target_passages']
        avg_actual = density_results['actual'].mean()
        qualified = (density_results['deviation'].abs() <= 20).sum()
        total = len(density_results)
        flow = TRAFFIC_DENSITIES[density]['target_flow']
        
        print(f"\n{density.upper()}:")
        print(f"  目标流量: {flow} veh/h")
        print(f"  目标通过: {target}辆/场景")
        print(f"  实际平均: {avg_actual:.1f}辆/场景")
        print(f"  合格率: {qualified}/{total} ({qualified/total*100:.1f}%)")
    
    # 保存报告
    report_file = Path(PROCESSED_DATA_DIR) / 'flow_validation_report.csv'
    Path(PROCESSED_DATA_DIR).mkdir(parents=True, exist_ok=True)
    results_df.to_csv(report_file, index=False)
    print(f"\n✅ 验证报告已保存: {report_file}")
    
    return results_df


def clean_data(df):
    """清洗数据"""
    print("\n" + "=" * 80)
    print("数据清洗")
    print("=" * 80)

    original_rows = len(df)
    original_tracks = df['trackId'].nunique()

    print(f"\n原始数据: {original_rows:,} 行, {original_tracks} 条轨迹")

    # 1. 过滤范围外数据
    print(f"\n[1/5] 过滤范围外数据 (>{COLLECTION_RADIUS}米)...")
    df_filtered = df[df['radius'] <= COLLECTION_RADIUS].copy()
    removed = original_rows - len(df_filtered)
    print(f"  移除 {removed:,} 行 ({removed / original_rows * 100:.1f}%)")

    # 2-3. 过滤短轨迹
    print(f"\n[2/5] 过滤短轨迹 (<2秒)...")
    min_length = 20
    track_lengths = df_filtered.groupby('trackId').size()
    valid_tracks = track_lengths[track_lengths >= min_length].index
    df_filtered = df_filtered[df_filtered['trackId'].isin(valid_tracks)]
    removed_tracks = original_tracks - len(valid_tracks)
    print(f"  移除 {removed_tracks} 条轨迹")

    # 4. 过滤静止车辆
    print(f"\n[3/5] 过滤静止车辆 (平均速度<0.5m/s)...")
    track_speeds = df_filtered.groupby('trackId')['speed'].mean()
    moving_tracks = track_speeds[track_speeds >= 0.5].index
    df_filtered = df_filtered[df_filtered['trackId'].isin(moving_tracks)]
    removed_static = len(valid_tracks) - len(moving_tracks)
    print(f"  移除 {removed_static} 条静止轨迹")

    # 5. 重新分配全局trackId
    print(f"\n[4/5] 重新分配全局trackId...")
    df_filtered['original_trackId'] = df_filtered['trackId']
    df_filtered['global_trackId'] = (
        df_filtered['scenario_id'].astype(str) + '_' +
        df_filtered['trackId'].astype(str)
    )
    track_mapping = {track: idx for idx, track in enumerate(df_filtered['global_trackId'].unique())}
    df_filtered['trackId'] = df_filtered['global_trackId'].map(track_mapping)
    df_filtered = df_filtered.drop(columns=['global_trackId'])

    final_rows = len(df_filtered)
    final_tracks = df_filtered['trackId'].nunique()

    print("\n" + "=" * 80)
    print("清洗结果")
    print("=" * 80)
    print(f"\n数据行数: {original_rows:,} → {final_rows:,} (保留{final_rows/original_rows*100:.1f}%)")
    print(f"轨迹数量: {original_tracks} → {final_tracks} (保留{final_tracks/original_tracks*100:.1f}%)")

    return df_filtered


def analyze_data(df):
    """分析清洗后的数据"""
    print("\n" + "=" * 80)
    print("数据分析")
    print("=" * 80)

    print(f"\n📊 基本统计:")
    print(f"  总行数: {len(df):,}")
    print(f"  轨迹数: {df['trackId'].nunique()}")
    print(f"  场景数: {df['scenario_id'].nunique()}")

    print(f"\n📈 运动统计:")
    print(f"  速度: {df['speed'].mean():.2f} m/s ({df['speed'].mean()*3.6:.1f} km/h)")
    print(f"  半径: {df['radius'].mean():.2f} m")

    print(f"\n🌦️ 天气分布:")
    for weather in sorted(df['weather'].unique()):
        count = len(df[df['weather'] == weather])
        tracks = df[df['weather'] == weather]['trackId'].nunique()
        print(f"  {weather:20s}: {count:7,} 行, {tracks:4} 轨迹")

    print(f"\n🚗 密度分布:")
    for density in TRAFFIC_DENSITIES.keys():
        if density in df['traffic_density'].values:
            count = len(df[df['traffic_density'] == density])
            tracks = df[df['traffic_density'] == density]['trackId'].nunique()
            print(f"  {density:12s}: {count:7,} 行, {tracks:4} 轨迹")

    print(f"\n🎯 行为分布:")
    for behavior in sorted(df['behavior_type'].unique()):
        count = len(df[df['behavior_type'] == behavior])
        tracks = df[df['behavior_type'] == behavior]['trackId'].nunique()
        avg_speed = df[df['behavior_type'] == behavior]['speed'].mean()
        print(f"  {behavior:10s}: {count:7,} 行, {tracks:4} 轨迹, {avg_speed:.2f} m/s")


def main():
    print("=" * 80)
    print("数据合并、清洗与验证 - v2")
    print("=" * 80)

    Path(PROCESSED_DATA_DIR).mkdir(parents=True, exist_ok=True)

    # 1. 加载数据
    df_raw = load_all_scenarios()
    if df_raw is None:
        return

    # 2. 验证流量
    flow_report = verify_flow_rates(df_raw)

    # 3. 清洗数据
    df_clean = clean_data(df_raw)

    # 4. 分析数据
    analyze_data(df_clean)

    # 5. 保存
    output_file = Path(PROCESSED_DATA_DIR) / 'carla_round_all.csv'
    df_clean.to_csv(output_file, index=False)

    print("\n" + "=" * 80)
    print("✅ 保存完成")
    print("=" * 80)
    print(f"\n文件: {output_file}")
    print(f"大小: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n下一步: 运行 3split_dataset_v2.py 划分数据集")


if __name__ == '__main__':
    main()
