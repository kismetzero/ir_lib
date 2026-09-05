import json

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
def bin_to_raw_timing(bin_str, timing_config, default_config):
    clean_bin = bin_str.replace(" ", "")
    
    agc_pulse = timing_config.get("agc_pulse", default_config.get("agc_pulse", {})).get("default", 9000)
    leader_pause = timing_config.get("leader_pause", default_config.get("leader_pause", {})).get("default", 4500)
    bit_pulse = timing_config.get("bit_pulse", default_config.get("bit_pulse", {})).get("default", 560)
    zero_pause = timing_config.get("zero_pause", default_config.get("zero_pause", {})).get("default", 560)
    one_pause = timing_config.get("one_pause", default_config.get("one_pause", {})).get("default", 1690)
    stop_pulse = timing_config.get("stop_pulse", default_config.get("stop_pulse", {})).get("default", 560)
    
    raw_array = [agc_pulse, leader_pause]
    
    for bit in clean_bin:
        raw_array.append(bit_pulse)
        if bit == '0':
            raw_array.append(zero_pause)
        elif bit == '1':
            raw_array.append(one_pause)
        else:
            raise ValueError(f"非法的二进制字符: {bit}")
        
    raw_array.append(stop_pulse)
    
    return raw_array

if __name__ == "__main__":
    json_data = load_json('data.json')
    nec_data = json_data.get("nec", {})
    default_timing = nec_data.get("default_timing_us", {})
    remotes = nec_data.get("remote", [])
    
    for remote in remotes:
        if not remote or "key_map" not in remote:
            continue
        
        remote_desc = remote.get("description", "Unknown Remote")
        key_maps = remote.get("key_map", [])
        remote_timing = remote.get("timing_us", default_timing)
        
        for key in key_maps:
            if not key.get("bin"):
                continue
            
            key_desc = key.get("description", "Unknown Key")
            bin_str = key["bin"]
            
            try:
                raw_timing = bin_to_raw_timing(bin_str, remote_timing, default_timing)
                raw_str = ",".join(map(str, raw_timing))
                key["timing"] = raw_str
            except Exception as e:
                    print(f"[Error] 处理 {remote_desc} - {key_desc} 时出错: {e}")

    save_json("new.json", json_data)
    