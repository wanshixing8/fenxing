"""
fractal_core.py — 分形系统核心共享模块
==========================================
统一提供包络函数 envelope_at() 和段衰减计算 compute_segment_decays()，
消除 auto_fractal.py / backtest_30min.py / backtest_riverbank.py / 
backtest_wind.py / wind_leaf_test.py 中的重复定义。

宪法约束：CONSTITUTION.md §6.1 原则 #3
"包络函数 envelope_at 是统一核心。各级别共用，不可各写一份。"

用法：
    from fractal_core import envelope_at, compute_segment_decays
"""


def envelope_at(phase, expand_ratio=1/3):
    """统一包络函数 — 所有级别共用。

    扩张阶段 (0 → expand_ratio)：0.2 → 1.0
    收缩阶段 (expand_ratio → 1.0)：1.0 → 0.015

    Args:
        phase: 0.0 ~ 1.0，当前投射在总波数中的位置
        expand_ratio: 扩张占总周期的比例，默认 1/3

    Returns:
        float: 0.015 ~ 1.0 的包络系数
    """
    if phase >= 1.0:
        return 0.015
    if phase < expand_ratio:
        t = phase / expand_ratio
        return 0.2 + 0.8 * t
    else:
        t = (phase - expand_ratio) / (1 - expand_ratio)
        return max(0.015, 1.0 - 0.985 * t)


def compute_segment_decays(ys):
    """计算段间振幅衰减比。

    decay[i] = clamp(amps[i+1] / amps[i], 0.3, 0.95)
    首段无前段可比时返回 0.618（黄金比例占位）。

    Args:
        ys: 生成器价格序列 (list of float)

    Returns:
        list of float: 段间衰减比，长度 = len(ys) - 2
    """
    pat = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    amps = [abs(d) for d in pat]
    decays = []
    for i in range(1, len(amps)):
        if amps[i - 1] > 0.001:
            decays.append(min(0.95, max(0.3, amps[i] / amps[i - 1])))
        else:
            decays.append(0.618)
    return decays
