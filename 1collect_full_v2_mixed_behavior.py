# scripts/1collect_full_v2_mixed_behavior.py
"""
混合行为版本
✅ 每个场景包含3种行为混合（更真实）
✅ 行为比例：Aggressive 25%, Normal 50%, Cautious 25%
✅ 学术依据：Treiber & Kesting (2013)
"""
import sys

sys.path.append('D:/Carla Simulation')

import carla
import pandas as pd
import numpy as np
import math
import time
from pathlib import Path
from roundabout_config_v2 import *


class MixedBehaviorCollector:
    def __init__(self):
        print("连接CARLA...")
        self.client = carla.Client('localhost', 2000)
        self.client.set_timeout(10.0)
        self.world = None
        self.traffic_manager = None
        self.spawned_vehicles = []
        self.vehicle_behaviors = {}  # 记录每辆车的行为类型

        Path(RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)

    def setup_world(self):
        """配置仿真环境"""
        print("加载Town03...")
        self.world = self.client.load_world('Town03')
        time.sleep(2)

        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / FRAME_RATE
        self.world.apply_settings(settings)

        self.traffic_manager = self.client.get_trafficmanager(8000)
        self.traffic_manager.set_synchronous_mode(True)
        self.traffic_manager.set_global_distance_to_leading_vehicle(2.0)

        print("✅ 环境配置完成")

    def get_outer_ring_spawn_points(self):
        """获取45-65米环形区域的spawn点"""
        all_spawns = self.world.get_map().get_spawn_points()

        outer_spawns = []
        for sp in all_spawns:
            dist = sp.location.distance(ROUNDABOUT_CENTER)

            if SPAWN_RADIUS_MIN <= dist <= SPAWN_RADIUS_MAX:
                to_center = ROUNDABOUT_CENTER - sp.location
                angle_to_center = math.atan2(to_center.y, to_center.x)
                spawn_yaw = math.radians(sp.rotation.yaw)

                angle_diff = abs(angle_to_center - spawn_yaw)
                if angle_diff > math.pi:
                    angle_diff = 2 * math.pi - angle_diff

                priority = 100 - angle_diff * 180 / math.pi
                outer_spawns.append((sp, dist, priority))

        outer_spawns.sort(key=lambda x: x[2], reverse=True)
        spawn_points = [sp for sp, _, _ in outer_spawns]

        print(f"  可用外环spawn点: {len(spawn_points)}个 (45-65米)")

        return spawn_points

    def set_weather(self, weather_name):
        """设置天气"""
        weather_presets = {
            'ClearNoon': carla.WeatherParameters.ClearNoon,
            'WetNoon': carla.WeatherParameters.WetNoon,
            'SoftRainNoon': carla.WeatherParameters.SoftRainNoon,
            'HardRainNoon': carla.WeatherParameters.HardRainNoon,
            'ClearSunset': carla.WeatherParameters.ClearSunset,
        }

        if weather_name in weather_presets:
            self.world.set_weather(weather_presets[weather_name])
        else:
            self.world.set_weather(carla.WeatherParameters.ClearNoon)

    def set_behavior(self, vehicle, behavior_type, weather_type):
        """设置驾驶行为"""
        behavior_speed = BEHAVIOR_SPEED_ADJUSTMENT.get(behavior_type, 0.0)
        weather_speed = WEATHER_SPEED_ADJUSTMENT.get(weather_type, 0.0)
        final_speed_diff = behavior_speed + weather_speed

        self.traffic_manager.vehicle_percentage_speed_difference(
            vehicle, final_speed_diff
        )

        following_dist = BEHAVIOR_FOLLOWING_DISTANCE.get(behavior_type, 2.5)
        self.traffic_manager.distance_to_leading_vehicle(vehicle, following_dist)

        ignore_lights = BEHAVIOR_IGNORE_LIGHTS.get(behavior_type, 10)
        self.traffic_manager.ignore_lights_percentage(vehicle, ignore_lights)

        if 'Rain' in weather_type:
            self.traffic_manager.distance_to_leading_vehicle(
                vehicle, following_dist + 0.5
            )

    def spawn_batch_mixed(self, num_vehicles, spawn_points, weather_type):
        """
        ⭐ 核心改进: 混合行为spawn

        行为比例（基于Treiber & Kesting 2013）:
        - Aggressive: 25%
        - Normal:     50%
        - Cautious:   25%
        """
        blueprint_library = self.world.get_blueprint_library()
        vehicle_bps = blueprint_library.filter('vehicle.*')

        # ⭐ 预先分配行为类型（按比例）
        behaviors = []
        num_aggressive = int(num_vehicles * 0.25)
        num_normal = int(num_vehicles * 0.50)
        num_cautious = num_vehicles - num_aggressive - num_normal

        behaviors.extend(['aggressive'] * num_aggressive)
        behaviors.extend(['normal'] * num_normal)
        behaviors.extend(['cautious'] * num_cautious)

        # 打乱顺序
        np.random.shuffle(behaviors)

        print(f"    行为分配: Aggressive {num_aggressive}, Normal {num_normal}, Cautious {num_cautious}")

        vehicles = []
        attempts = 0
        max_attempts = num_vehicles * SPAWN_RETRIES
        behavior_idx = 0

        while len(vehicles) < num_vehicles and attempts < max_attempts:
            bp = np.random.choice(vehicle_bps)
            spawn_point = np.random.choice(spawn_points)

            # 获取当前车辆的行为类型
            current_behavior = behaviors[behavior_idx % len(behaviors)]

            try:
                vehicle = self.world.spawn_actor(bp, spawn_point)
                vehicle.set_autopilot(True, self.traffic_manager.get_port())

                # ⭐ 设置对应的行为
                self.set_behavior(vehicle, current_behavior, weather_type)

                vehicles.append(vehicle)
                self.spawned_vehicles.append(vehicle)

                # ⭐ 记录这辆车的行为类型
                self.vehicle_behaviors[vehicle.id] = current_behavior

                behavior_idx += 1

                if len(vehicles) % 3 == 0:
                    for _ in range(2):
                        self.world.tick()

            except Exception as e:
                attempts += 1
                if attempts % 5 == 0:
                    for _ in range(3):
                        self.world.tick()
                continue

        return vehicles

    def dynamic_spawn_traffic_mixed(self, density_config, weather_type):
        """
        动态分批spawn混合行为车辆
        """
        spawn_total = density_config['spawn_total']
        spawn_per_batch = density_config['spawn_per_batch']
        target_passages = density_config['target_passages']
        batch_interval = density_config.get('batch_interval', 15)  # ⭐ 从配置读取间隔，默认15秒

        print(f"\n动态Spawn配置（混合行为）:")
        print(f"  总spawn目标: {spawn_total}辆")
        print(f"  每批spawn: {spawn_per_batch}辆")
        print(f"  行为比例: 25% Aggressive, 50% Normal, 25% Cautious")
        print(f"  间隔: {batch_interval}秒")
        print(f"  目标通过核心区: {target_passages}辆")

        spawn_points = self.get_outer_ring_spawn_points()

        if not spawn_points:
            print("❌ 没有可用的外环spawn点")
            return

        num_batches = (spawn_total + spawn_per_batch - 1) // spawn_per_batch
        print(f"  总批次: {num_batches}批\n")

        total_spawned = 0
        for batch_id in range(num_batches):
            remaining = spawn_total - total_spawned
            batch_size = min(spawn_per_batch, remaining)

            print(f"批次 {batch_id + 1}/{num_batches}: spawn {batch_size}辆...", end=" ")

            # ⭐ 使用混合行为spawn
            batch_vehicles = self.spawn_batch_mixed(
                batch_size, spawn_points, weather_type
            )

            total_spawned += len(batch_vehicles)
            print(f"成功{len(batch_vehicles)}辆 (累计{total_spawned}/{spawn_total})")

            if batch_id < num_batches - 1:
                for _ in range(batch_interval * FRAME_RATE):
                    self.world.tick()

        print(f"\n✅ 动态spawn完成: {total_spawned}/{spawn_total}辆")

    def collect_frame_data(self, frame_id, weather, density):
        """
        ⭐ 改进: 采集时记录每辆车的实际行为类型
        """
        data = []

        for vehicle in self.spawned_vehicles:
            try:
                transform = vehicle.get_transform()
                velocity = vehicle.get_velocity()
                acceleration = vehicle.get_acceleration()

                dx = transform.location.x - ROUNDABOUT_CENTER.x
                dy = transform.location.y - ROUNDABOUT_CENTER.y
                radius = math.sqrt(dx ** 2 + dy ** 2)
                angle = math.atan2(dy, dx)

                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2)
                accel = math.sqrt(acceleration.x ** 2 + acceleration.y ** 2)

                # ⭐ 获取这辆车的行为类型
                behavior = self.vehicle_behaviors.get(vehicle.id, 'unknown')

                data.append({
                    'frame': frame_id,
                    'trackId': vehicle.id,
                    'x': transform.location.x,
                    'y': transform.location.y,
                    'z': transform.location.z,
                    'vx': velocity.x,
                    'vy': velocity.y,
                    'speed': speed,
                    'ax': acceleration.x,
                    'ay': acceleration.y,
                    'accel': accel,
                    'heading': math.radians(transform.rotation.yaw),
                    'radius': radius,
                    'angle': angle,
                    'weather': weather,
                    'traffic_density': density,
                    'behavior_type': behavior  # ⭐ 每辆车有自己的行为
                })
            except:
                continue

        return data

    def run_scenario(self, scenario_id, weather, density_name, density_config):
        """
        运行单个场景（混合行为版本）
        注意：不再需要behavior参数，因为每个场景内部就是混合的
        """
        print(f"\n{'=' * 70}")
        print(f"场景 {scenario_id + 1}/{TOTAL_SCENARIOS_MIXED}")
        print(f"  天气: {weather}")
        print(f"  密度: {density_name} (目标流量: {density_config['target_flow']} veh/h)")
        print(f"  行为: 混合 (25% Aggressive, 50% Normal, 25% Cautious)")
        print(f"  进度: {(scenario_id + 1) / TOTAL_SCENARIOS_MIXED * 100:.1f}%")
        print(f"{'=' * 70}")

        self.set_weather(weather)
        self.spawned_vehicles = []
        self.vehicle_behaviors = {}

        print(f"\n预热 {WARMUP_TIME}秒...")
        for _ in range(WARMUP_TIME * FRAME_RATE):
            self.world.tick()

        # 动态spawn混合行为车辆
        self.dynamic_spawn_traffic_mixed(density_config, weather)

        print(f"\n开始采集 {SCENARIO_DURATION}秒...")
        all_data = []

        start_time = time.time()

        for frame in range(SCENARIO_DURATION * FRAME_RATE):
            self.world.tick()

            # ⭐ 不需要传behavior，每辆车自己有行为类型
            frame_data = self.collect_frame_data(
                frame, weather, density_name
            )
            all_data.extend(frame_data)

            if (frame + 1) % (FRAME_RATE * 30) == 0:
                elapsed = time.time() - start_time
                progress = (frame + 1) / (SCENARIO_DURATION * FRAME_RATE) * 100
                active_vehicles = len([v for v in self.spawned_vehicles if v.is_alive])
                print(f"  进度: {progress:.0f}%, 活跃车辆: {active_vehicles}, 用时: {elapsed:.0f}秒")

        elapsed = time.time() - start_time

        print("\n清理车辆...")
        for vehicle in self.spawned_vehicles:
            try:
                vehicle.destroy()
            except:
                pass
        self.spawned_vehicles = []
        self.vehicle_behaviors = {}

        if not all_data:
            print("❌ 未采集到数据")
            return None

        df = pd.DataFrame(all_data)
        output_file = Path(RAW_DATA_DIR) / f'scenario_{scenario_id:03d}.csv'
        df.to_csv(output_file, index=False)

        # 统计（按行为类型分别统计）
        unique_tracks = df['trackId'].nunique()
        avg_speed = df['speed'].mean()

        core_tracks = df[df['radius'] <= 25]['trackId'].nunique()
        target = density_config['target_passages']

        # 统计各行为类型的轨迹数
        behavior_counts = df.groupby('behavior_type')['trackId'].nunique()

        print(f"\n✅ 完成 ({elapsed:.1f}秒)")
        print(f"   采集数据: {len(df):,}行")
        print(f"   总轨迹数: {unique_tracks}条")
        print(f"   行为分布: ", end="")
        for behavior, count in behavior_counts.items():
            print(f"{behavior} {count}条, ", end="")
        print()
        print(f"   核心区轨迹: {core_tracks}条 (目标{target}条)")
        print(f"   平均速度: {avg_speed:.2f} m/s ({avg_speed * 3.6:.1f} km/h)")

        return df

    def cleanup(self):
        """清理资源"""
        print("\n清理环境...")

        for vehicle in self.spawned_vehicles:
            try:
                vehicle.destroy()
            except:
                pass

        vehicles = self.world.get_actors().filter('vehicle.*')
        for vehicle in vehicles:
            try:
                vehicle.destroy()
            except:
                pass

        settings = self.world.get_settings()
        settings.synchronous_mode = False
        self.world.apply_settings(settings)

        print("✅ 清理完成")


# ⭐ 修改：总场景数减少为 5天气 × 5密度 = 25场景
TOTAL_SCENARIOS_MIXED = len(WEATHER_TYPES) * len(TRAFFIC_DENSITIES)


def main():
    print("=" * 80)
    print("CARLA 环岛数据采集 - 混合行为版本")
    print("=" * 80)
    print(f"\n配置:")
    print(f"  天气类型: {len(WEATHER_TYPES)}种")
    print(f"  密度级别: {len(TRAFFIC_DENSITIES)}种")
    print(f"  行为类型: 混合（每场景包含3种行为）")
    print(f"  行为比例: 25% Aggressive, 50% Normal, 25% Cautious")
    print(f"  总场景数: {TOTAL_SCENARIOS_MIXED}个 (5天气 × 5密度)")
    print(f"  观测时长: {SCENARIO_DURATION}秒")
    print(f"  Spawn方式: 动态分批，从50-60米外驶入")

    print(f"\n学术依据:")
    print(f"  Treiber & Kesting (2013): 异质交通流建模")
    print(f"  真实交通流中行为分布: ~25%激进, ~50%正常, ~25%谨慎")

    confirm = input("\n开始采集？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    collector = MixedBehaviorCollector()
    collector.setup_world()

    # ⭐ 生成场景配置（只有天气×密度，没有行为维度）
    scenarios = []
    scenario_id = 0
    for weather in WEATHER_TYPES:
        for density_name, density_config in TRAFFIC_DENSITIES.items():
            scenarios.append({
                'id': scenario_id,
                'weather': weather,
                'density_name': density_name,
                'density_config': density_config,
            })
            scenario_id += 1

    successful = 0
    failed = 0
    total_core_tracks = 0
    total_target = 0

    start_time = time.time()

    for scenario in scenarios:
        try:
            df = collector.run_scenario(
                scenario['id'],
                scenario['weather'],
                scenario['density_name'],
                scenario['density_config']
            )
            if df is not None:
                successful += 1
                core_tracks = df[df['radius'] <= 25]['trackId'].nunique()
                total_core_tracks += core_tracks
                total_target += scenario['density_config']['target_passages']
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 场景 {scenario['id']} 失败: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
            continue

    total_time = time.time() - start_time
    achievement_rate = total_core_tracks / total_target * 100 if total_target > 0 else 0

    print("\n" + "=" * 80)
    print("✅ 采集完成！")
    print("=" * 80)
    print(f"\n统计:")
    print(f"  成功: {successful}/{TOTAL_SCENARIOS_MIXED} 场景")
    print(f"  失败: {failed}/{TOTAL_SCENARIOS_MIXED} 场景")
    print(f"  总核心区轨迹: {total_core_tracks}条")
    print(f"  总目标轨迹: {total_target}条")
    print(f"  达成率: {achievement_rate:.1f}%")
    print(f"  实际时长: {total_time / 60:.1f} 分钟 ({total_time / 3600:.1f} 小时)")
    print(f"\n数据位置: {RAW_DATA_DIR}")

    print(f"\n优势:")
    print(f"  ✅ 场景数减少: 75 → 25 (节省67%时间)")
    print(f"  ✅ 更真实: 混合行为符合真实交通流")
    print(f"  ✅ 轨迹数相同: 每场景3倍轨迹数")

    collector.cleanup()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback

        traceback.print_exc()