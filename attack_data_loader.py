"""
ATT&CK 数据下载和解析脚本
从MITRE官方下载最新的ATT&CK框架数据
"""

import json
import requests
from typing import Dict, List, Any
import os
from project_paths import DATA_PROCESSED_DIR, ensure_standard_directories


def download_attack_data(version: str = "15.1") -> Dict[str, Any]:
    """
    从MITRE官方下载ATT&CK数据
    
    Args:
        version: ATT&CK版本号
    
    Returns:
        ATT&CK JSON数据
    """
    url = f"https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
    
    print(f"正在下载ATT&CK数据: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"下载成功，共 {len(data.get('objects', []))} 个对象")
        return data
    except Exception as e:
        print(f"下载失败: {e}")
        return None


def parse_attack_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析ATT&CK原始数据，提取战术、技术、子技术信息
    
    Args:
        raw_data: MITRE ATT&CK原始JSON数据
    
    Returns:
        解析后的结构化数据
    """
    tactics = {}
    techniques = {}
    sub_techniques = {}
    relationships = []
    
    # 第一遍：提取所有对象
    for obj in raw_data.get('objects', []):
        obj_type = obj.get('type')
        
        if obj_type == 'x-mitre-tactic':
            # 战术
            tactic_id = obj.get('x_mitre_shortname', '')
            external_id = ''
            for ref in obj.get('external_references', []):
                if ref.get('source_name') == 'mitre-attack':
                    external_id = ref.get('external_id', '')
                    break
            
            tactics[external_id] = {
                'id': external_id,
                'name': obj.get('name', ''),
                'description': obj.get('description', ''),
                'shortname': tactic_id,
                'techniques': []
            }
        
        elif obj_type == 'attack-pattern':
            # 技术或子技术
            external_id = ''
            for ref in obj.get('external_references', []):
                if ref.get('source_name') == 'mitre-attack':
                    external_id = ref.get('external_id', '')
                    break
            
            if not external_id:
                continue
            
            is_sub_technique = obj.get('x_mitre_is_subtechnique', False)
            
            technique_data = {
                'id': external_id,
                'name': obj.get('name', ''),
                'description': obj.get('description', ''),
                'kill_chain_phases': obj.get('kill_chain_phases', []),
                'is_sub_technique': is_sub_technique
            }
            
            if is_sub_technique:
                sub_techniques[external_id] = technique_data
            else:
                techniques[external_id] = technique_data
        
        elif obj_type == 'relationship':
            # 关系
            relationships.append(obj)
    
    # 第二遍：建立关系
    # 1. 将技术关联到战术
    for tech_id, tech_data in techniques.items():
        for phase in tech_data.get('kill_chain_phases', []):
            if phase.get('kill_chain_name') == 'mitre-attack':
                tactic_shortname = phase.get('phase_name', '')
                # 查找对应的战术
                for tactic_id, tactic_data in tactics.items():
                    if tactic_data.get('shortname') == tactic_shortname:
                        tactic_data['techniques'].append({
                            'id': tech_id,
                            'name': tech_data['name'],
                            'description': tech_data['description'],
                            'sub_techniques': []
                        })
                        break
    
    # 2. 将子技术关联到父技术
    for sub_id, sub_data in sub_techniques.items():
        # 子技术ID格式为 TXXXX.XXX
        if '.' in sub_id:
            parent_id = sub_id.split('.')[0]
            
            # 查找父技术并添加子技术
            for tactic_data in tactics.values():
                for tech in tactic_data.get('techniques', []):
                    if tech['id'] == parent_id:
                        tech['sub_techniques'].append({
                            'id': sub_id,
                            'name': sub_data['name'],
                            'description': sub_data['description']
                        })
                        break
    
    return {
        'tactics': list(tactics.values()),
        'metadata': {
            'total_tactics': len(tactics),
            'total_techniques': len(techniques),
            'total_sub_techniques': len(sub_techniques)
        }
    }


def save_parsed_data(data: Dict[str, Any], output_path: str):
    """
    保存解析后的数据
    
    Args:
        data: 解析后的数据
        output_path: 输出文件路径
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"数据已保存到: {output_path}")


def load_parsed_data(data_path: str) -> Dict[str, Any]:
    """
    加载已解析的数据
    
    Args:
        data_path: 数据文件路径
    
    Returns:
        解析后的数据
    """
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_technique_count(data: Dict[str, Any]) -> Dict[str, int]:
    """
    统计技术数量
    
    Args:
        data: 解析后的数据
    
    Returns:
        统计信息
    """
    total_techniques = 0
    total_sub_techniques = 0
    
    for tactic in data.get('tactics', []):
        for tech in tactic.get('techniques', []):
            total_techniques += 1
            total_sub_techniques += len(tech.get('sub_techniques', []))
    
    return {
        'tactics': len(data.get('tactics', [])),
        'techniques': total_techniques,
        'sub_techniques': total_sub_techniques
    }


def main():
    """
    主函数
    """
    # 下载数据
    ensure_standard_directories()
    raw_data = download_attack_data()
    
    if not raw_data:
        print("下载失败，退出")
        return
    
    # 解析数据
    parsed_data = parse_attack_data(raw_data)
    
    # 保存数据
    output_path = str(DATA_PROCESSED_DIR / "attack_data.json")
    save_parsed_data(parsed_data, output_path)
    
    # 统计信息
    stats = get_technique_count(parsed_data)
    print(f"\n数据统计:")
    print(f"战术数量: {stats['tactics']}")
    print(f"技术数量: {stats['techniques']}")
    print(f"子技术数量: {stats['sub_techniques']}")
    
    # 显示示例
    print(f"\n示例数据:")
    if parsed_data['tactics']:
        first_tactic = parsed_data['tactics'][0]
        print(f"第一个战术: {first_tactic['id']} - {first_tactic['name']}")
        if first_tactic['techniques']:
            first_tech = first_tactic['techniques'][0]
            print(f"  第一个技术: {first_tech['id']} - {first_tech['name']}")
            if first_tech['sub_techniques']:
                first_sub = first_tech['sub_techniques'][0]
                print(f"    第一个子技术: {first_sub['id']} - {first_sub['name']}")


if __name__ == "__main__":
    main()
