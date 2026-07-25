"""CZSC 拐点检测模块 — 缠中说禅 分型识别 + 包含处理

流程:
  1. K线包含处理 (向上/向下合并)
  2. 顶底分型识别
  3. 分型过滤 (5根不含K线才成笔)
  4. 输出拐点序列 → 丢给河岸投射引擎

与当前 find_fractals_hl 对比:
  - window=5 用左右5根极值 → CZSC 用3根分型+包含处理
  - CZSC 更抗噪 (K线合并后假拐点少)
  - CZSC 天然产出 H-L-H-L 交替序列 → 匹配河岸模型
"""

def czsc_include_merge(bars, direction='up'):
    """K线包含处理。
    
    bars: [(high, low), ...] 的列表
    direction: 'up' 向上处理 (取高高+高低), 'down' 向下处理 (取低高+低低)
    
    返回: 合并后的 [(high, low), ...]
    """
    if len(bars) < 2:
        return bars
    
    result = [bars[0]]
    for i in range(1, len(bars)):
        prev_h, prev_l = result[-1]
        curr_h, curr_l = bars[i]
        
        # 判断包含关系：当前K线完全被前一根包含 或 包含前一根
        if curr_h >= prev_h and curr_l <= prev_l:
            # 当前包含前一根 (或相等)
            if direction == 'up':
                # 向上：取高高+高低 (两个高点中较高, 两个低点中较高)
                merged = (max(curr_h, prev_h), max(curr_l, prev_l))
            else:
                # 向下：取低高+低低
                merged = (min(curr_h, prev_h), min(curr_l, prev_l))
            result[-1] = merged
        elif curr_h <= prev_h and curr_l >= prev_l:
            # 前一根包含当前
            if direction == 'up':
                merged = (max(curr_h, prev_h), max(curr_l, prev_l))
            else:
                merged = (min(curr_h, prev_h), min(curr_l, prev_l))
            result[-1] = merged
        else:
            # 无包含 → 判断方向切换
            if curr_h > prev_h:
                direction = 'up'
            elif curr_h < prev_h:
                direction = 'down'
            result.append(bars[i])
    
    return result


def czsc_find_fx(merged_bars):
    """在包含处理后的K线上识别顶底分型。
    
    顶分型: 中间K线高点最高, 低点也最高 (三明治形状)
    底分型: 中间K线低点最低, 高点也最低
    
    返回: [(index, price, 'H'/'L'), ...] 按时间排序
    """
    if len(merged_bars) < 3:
        return []
    
    pivots = []
    for i in range(1, len(merged_bars) - 1):
        h_l, h_m, h_r = merged_bars[i-1][0], merged_bars[i][0], merged_bars[i+1][0]
        l_l, l_m, l_r = merged_bars[i-1][1], merged_bars[i][1], merged_bars[i+1][1]
        
        # 顶分型: 中间高点是最高, 同时低点也最高
        if h_m > h_l and h_m > h_r and l_m >= l_l and l_m >= l_r:
            pivots.append((i, h_m, 'H'))
        # 底分型: 中间低点是最低, 同时高点也最低
        elif l_m < l_l and l_m < l_r and h_m <= h_l and h_m <= h_r:
            pivots.append((i, l_m, 'L'))
    
    return pivots


def czsc_filter_bi(pivots, min_distance=4):
    """笔过滤：相邻顶底分型之间至少需 min_distance 根K线（不含两端）。
    
    返回: 过滤后的拐点序列
    """
    if len(pivots) < 2:
        return pivots
    
    result = [pivots[0]]
    for p in pivots[1:]:
        last = result[-1]
        # 必须不同类型 且 距离足够
        if p[2] != last[2] and p[0] - last[0] >= min_distance:
            result.append(p)
        # 同向取更显著的
        elif p[2] == last[2]:
            if (p[2] == 'H' and p[1] > last[1]) or (p[2] == 'L' and p[1] < last[1]):
                result[-1] = p
    
    # 确保最后两个是 H-L 交替
    while len(result) >= 2 and result[-1][2] == result[-2][2]:
        result.pop()
    
    return result


def czsc_detect_pivots(raw_bars, direction='up'):
    """一站式 CZSC 拐点检测。
    
    raw_bars: K线数据，格式可以是:
      - [(high, low), ...]  
      - [{'h': h, 'l': l}, ...]
      - [[time, open, close, high, low, vol], ...]
    
    返回: [(index, price, 'H'/'L'), ...] 原始K线中的索引+拐点
    """
    # 提取 (high, low)
    bars = []
    for b in raw_bars:
        if isinstance(b, (list, tuple)):
            if len(b) >= 5:
                bars.append((float(b[3]), float(b[4])))  # 腾讯K线格式
            elif len(b) >= 2:
                bars.append((float(b[0]), float(b[1])))
        elif isinstance(b, dict):
            bars.append((float(b.get('h', b.get('high', 0))), 
                         float(b.get('l', b.get('low', 0)))))
        else:
            raise ValueError(f"无法解析K线格式: {type(b)}")
    
    # 包含处理
    merged = czsc_include_merge(bars, direction)
    
    # 分型检测
    pivots = czsc_find_fx(merged)
    
    # 笔过滤
    pivots = czsc_filter_bi(pivots)
    
    # 将合并后的索引映射回原始索引 (近似)
    # 取合并组的中点作为对应原始索引
    # 简化：直接用合并索引，调用方自行映射
    return pivots, merged


if __name__ == "__main__":
    # 测试：用今天的 601985 数据
    test_bars = [
        [0,0,0,9.11,9.07], [0,0,0,9.10,9.08], [0,0,0,9.12,9.09],
        [0,0,0,9.10,9.07], [0,0,0,9.09,9.06], [0,0,0,9.08,9.05],
        [0,0,0,9.06,9.03], [0,0,0,9.04,9.01], [0,0,0,9.02,9.00],
        [0,0,0,9.01,8.98], [0,0,0,9.00,8.97], [0,0,0,8.99,8.96],
        [0,0,0,8.98,8.95], [0,0,0,8.97,8.94], [0,0,0,8.96,8.93],
        [0,0,0,8.95,8.92], [0,0,0,8.94,8.91], [0,0,0,8.93,8.90],
        [0,0,0,8.92,8.89], [0,0,0,8.91,8.88],
    ]
    
    pivots, merged = czsc_detect_pivots(test_bars)
    print(f"原始K线: {len(test_bars)} → 合并后: {len(merged)}")
    print(f"拐点: {len(pivots)} 个")
    for idx, price, kind in pivots:
        mh, ml = merged[idx]
        print(f"  [{idx}] {kind} price={price:.2f} (合并K线 H={mh:.2f} L={ml:.2f})")
