# scripts/test_mixed_behavior_v2.py
"""
改进版快速测试脚本
✅ 避免崩溃
✅ 扩大spawn范围（45-65米）
✅ 完整显示结果
"""
import sys

sys.path.append('D:/Carla Simulation')

import carla
import pandas as pd
import numpy as np
import math
import time
from pathlib import Path

# ===== 简化配置 =====
ROUNDABOUT_CENTER = carla.Location(x=0.0, y=0.0, z=0.0)
SPAWN_RADIUS_MIN = 45.0  # ⭐ 扩大到45米
SPAWN_RADIUS_MAX = 65.0  # ⭐ 扩大到65米
FRAME_RATE = 10
SCENARIO_DURATION = 60
WARMUP_TIME = 5
SPAWN_INTERVAL = 10

BEHAVIOR_SPEED_ADJUSTMENT = {
    'aggressive': -20.0,
    'normal': 0.0,
    'cautious': 30.0,
}

BEHAVIOR_FOLLOWING_DISTANCE = {
    'aggressive': 1.5,
    'normal': 2.5,
    'cautious': 4.0,
}

print("=" * 80)
print("🧪 混合行为快速测试 v2 (改进版)")
print("=" * 80)
print("\n配置:")
print("  场景时长: 60秒")
print("  Spawn范围: 45-65米（扩大范围）")
print("  Spawn总数: 20辆")
print("  行为比例: 25% Aggressive, 50% Normal, 25% Cautious")
print("  预计时间: 3-5分钟\n")

try:
    # ===== 连接CARLA =====
    print("1️⃣ 连接CARLA...")
    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    print("✅ 连接成功\n")

    # ===== 加载地图 =====
    print("2️⃣ 加载Town03...")
    world = client.load_world('Town03')
    time.sleep(2)

    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.1
    world.apply_settings(settings)

    traffic_manager = client.get_trafficmanager(8000)
    traffic_manager.set_synchronous_mode(True)
    print("✅ 地图加载完成\n")

    # ===== 获取spawn点 =====
    print("3️⃣ 获取spawn点...")
    all_spawns = world.get_map().get_spawn_points()
    outer_spawns = []

    for sp in all_spawns:
        dist = sp.location.distance(ROUNDABOUT_CENTER)
        if SPAWN_RADIUS_MIN <= dist <= SPAWN_RADIUS_MAX:
            outer_spawns.append(sp)

    print(f"✅ 找到 {len(outer_spawns)} 个spawn点 (45-65米)\n")

    # ===== 设置天气 =====
    print("4️⃣ 设置天气...")
    world.set_weather(carla.WeatherParameters.ClearNoon)
    print("✅ 天气设置完成\n")

    # ===== Spawn混合行为车辆 =====
    print("5️⃣ Spawn混合行为车辆...")
    print("  目标: 20辆 (5 Aggressive + 10 Normal + 5 Cautious)\n")

    num_vehicles = 20
    num_aggressive = int(num_vehicles * 0.25)
    num_normal = int(num_vehicles * 0.50)
    num_cautious = num_vehicles - num_aggressive - num_normal

    behaviors = (
            ['aggressive'] * num_aggressive +
            ['normal'] * num_normal +
            ['cautious'] * num_cautious
    )
    np.random.shuffle(behaviors)

    print(f"  行为分配: {num_aggressive} Aggressive + {num_normal} Normal + {num_cautious} Cautious")

    blueprint_library = world.get_blueprint_library()
    vehicle_bps = blueprint_library.filter('vehicle.*')

    spawned_vehicles = []
    vehicle_behaviors = {}

    for i, behavior in enumerate(behaviors):
        attempts = 0
        max_attempts = 20

        while attempts < max_attempts:
            bp = np.random.choice(vehicle_bps)
            spawn_point = np.random.choice(outer_spawns)

            try:
                vehicle = world.spawn_actor(bp, spawn_point)
                vehicle.set_autopilot(True, traffic_manager.get_port())

                speed_adj = BEHAVIOR_SPEED_ADJUSTMENT[behavior]
                traffic_manager.vehicle_percentage_speed_difference(vehicle, speed_adj)

                following_dist = BEHAVIOR_FOLLOWING_DISTANCE[behavior]
                traffic_manager.distance_to_leading_vehicle(vehicle, following_dist)

                spawned_vehicles.append(vehicle)
                vehicle_behaviors[vehicle.id] = behavior

                print(f"  ✓ 车辆 {i + 1}/20: {behavior}")

                if len(spawned_vehicles) % 3 == 0:
                    for _ in range(2):
                        world.tick()

                break

            except Exception as e:
                attempts += 1
                if attempts % 5 == 0:
                    for _ in range(3):
                        world.tick()
                continue

        if attempts >= max_attempts:
            print(f"  ⚠️ 车辆 {i + 1} spawn失败")

    print(f"\n✅ 成功spawn {len(spawned_vehicles)}/20 辆车\n")

    # ===== 预热 =====
    print(f"6️⃣ 预热 {WARMUP_TIME}秒...")
    for _ in range(WARMUP_TIME * FRAME_RATE):
        world.tick()
    print("✅ 预热完成\n")

    # ===== 采集数据 =====
    print(f"7️⃣ 采集数据 {SCENARIO_DURATION}秒...")
    all_data = []

    for frame in range(SCENARIO_DURATION * FRAME_RATE):
        world.tick()

        for vehicle in spawned_vehicles:
            try:
                transform = vehicle.get_transform()
                velocity = vehicle.get_velocity()

                dx = transform.location.x - ROUNDABOUT_CENTER.x
                dy = transform.location.y - ROUNDABOUT_CENTER.y
                radius = math.sqrt(dx ** 2 + dy ** 2)

                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2)
                behavior = vehicle_behaviors.get(vehicle.id, 'unknown')

                all_data.append({
                    'frame': frame,
                    'trackId': vehicle.id,
                    'x': transform.location.x,
                    'y': transform.location.y,
                    'speed': speed,
                    'radius': radius,
                    'behavior_type': behavior
                })
            except:
                continue

        if (frame + 1) % (FRAME_RATE * 15) == 0:
            progress = (frame + 1) / (SCENARIO_DURATION * FRAME_RATE) * 100
            print(f"  进度: {progress:.0f}%")

    print("✅ 采集完成\n")

    # ⭐ 先分析数据，再清理车辆（避免崩溃影响结果显示）
    print("=" * 80)
    print("📊 测试结果分析")
    print("=" * 80)

    if not all_data:
        print("\n❌ 未采集到数据")
    else:
        df = pd.DataFrame(all_data)

        print(f"\n基本统计:")
        print(f"  总数据点: {len(df):,} 行")
        print(f"  总轨迹数: {df['trackId'].nunique()} 条")
        print(f"  平均速度: {df['speed'].mean():.2f} m/s ({df['speed'].mean() * 3.6:.1f} km/h)")

        print(f"\n✅ 行为分布验证:")
        behavior_stats = df.groupby('behavior_type').agg({
            'trackId': 'nunique',
            'speed': 'mean'
        }).round(2)

        for behavior, row in behavior_stats.iterrows():
            track_count = int(row['trackId'])
            avg_speed = row['speed']
            percentage = track_count / df['trackId'].nunique() * 100

            if behavior == 'aggressive':
                expected = "25%"
                status = "✅" if 15 <= percentage <= 35 else "⚠️"
            elif behavior == 'normal':
                expected = "50%"
                status = "✅" if 40 <= percentage <= 60 else "⚠️"
            elif behavior == 'cautious':
                expected = "25%"
                status = "✅" if 15 <= percentage <= 35 else "⚠️"
            else:
                expected = "N/A"
                status = "❓"

            print(
                f"  {status} {behavior:10s}: {track_count:2d}条 ({percentage:5.1f}%) - 预期{expected:>4s} - 速度{avg_speed:.2f} m/s")

        print(f"\n✅ 速度差异验证:")
        aggressive_speed = df[df['behavior_type'] == 'aggressive']['speed'].mean()
        normal_speed = df[df['behavior_type'] == 'normal']['speed'].mean()
        cautious_speed = df[df['behavior_type'] == 'cautious']['speed'].mean()

        print(f"  Aggressive: {aggressive_speed:.2f} m/s ({aggressive_speed * 3.6:.1f} km/h)")
        print(f"  Normal:     {normal_speed:.2f} m/s ({normal_speed * 3.6:.1f} km/h)")
        print(f"  Cautious:   {cautious_speed:.2f} m/s ({cautious_speed * 3.6:.1f} km/h)")

        if aggressive_speed > normal_speed > cautious_speed:
            print(f"  ✅ 速度关系正确: Aggressive > Normal > Cautious")
            speed_check = True
        else:
            print(f"  ⚠️ 速度关系异常（可能样本太小）")
            speed_check = False

        print(f"\n核心区统计:")
        core_tracks = df[df['radius'] <= 25]['trackId'].nunique()
        print(f"  进入核心区(25米内): {core_tracks} 条轨迹")

        # 保存测试数据
        output_file = Path('D:/Carla Simulation/test_mixed_behavior.csv')
        df.to_csv(output_file, index=False)
        print(f"\n💾 测试数据已保存: {output_file}")

        print("\n" + "=" * 80)
        print("🎉 测试完成！")
        print("=" * 80)

        print("\n结论:")
        if df['trackId'].nunique() >= 15:
            print("  ✅ Spawn成功率良好")
            spawn_check = True
        else:
            print("  ⚠️ Spawn成功率偏低")
            spawn_check = False

        behavior_counts = df.groupby('behavior_type')['trackId'].nunique()
        if len(behavior_counts) == 3:
            print("  ✅ 混合行为功能正常")
            behavior_check = True
        else:
            print("  ⚠️ 混合行为功能异常")
            behavior_check = False

        if speed_check:
            print("  ✅ 行为参数设置正确")
        else:
            print("  ⚠️ 行为参数需要调整")

        print("\n" + "=" * 80)
        if spawn_check and behavior_check and speed_check:
            print("✅✅✅ 所有测试通过！可以开始正式采集！")
            print("运行: python 1collect_full_v2_mixed_behavior.py")
        else:
            print("⚠️ 部分测试未通过，建议重新测试或调整参数")
        print("=" * 80)

    # ===== 最后清理车辆 =====
    print("\n8️⃣ 清理车辆...")
    for vehicle in spawned_vehicles:
        try:
            vehicle.destroy()
        except:
            pass  # 忽略错误

    # 清理所有车辆
    try:
        vehicles = world.get_actors().filter('vehicle.*')
        for vehicle in vehicles:
            try:
                vehicle.destroy()
            except:
                pass
    except:
        pass

    # 恢复设置
    try:
        settings = world.get_settings()
        settings.synchronous_mode = False
        world.apply_settings(settings)
    except:
        pass

    print("✅ 清理完成\n")

except KeyboardInterrupt:
    print("\n\n⚠️ 用户中断")
except Exception as e:
    print(f"\n\n❌ 错误: {e}")
    import traceback

    traceback.print_exc()
finally:
    print("\n测试结束")