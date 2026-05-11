import json
import os
import datetime
import logging

logger = logging.getLogger(__name__)

VIP_FILE = os.path.abspath("data/vip_users.json")

def load_vip_data():
    if not os.path.exists(VIP_FILE):
        return {"vips": {}, "config": {"pix_key": "+5511981826659", "monthly_price": 19.90}, "allowed_groups": []}
    try:
        with open(VIP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"vips": {}, "config": {"pix_key": "+5511981826659", "monthly_price": 19.90}, "allowed_groups": []}

def save_vip_data(data):
    try:
        with open(VIP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"[VIP] Erro ao salvar dados: {e}")
        return False

def is_vip(jid):
    # Limpa o JID para lidar com multi-device (remove :0, :1 etc)
    clean_jid = jid.split(':')[0]
    if '@' not in clean_jid and '@' in jid:
        clean_jid += '@' + jid.split('@')[1]
    elif '@' not in clean_jid:
        clean_jid += '@s.whatsapp.net'

    data = load_vip_data()
    # Criador é sempre VIP
    owner = data.get("config", {}).get("owner_number", "5511981826659@s.whatsapp.net")
    if clean_jid == owner or jid == owner:
        return True
        
    # Verifica se o JID está na lista e se a assinatura não expirou
    vip_info = data.get("vips", {}).get(clean_jid) or data.get("vips", {}).get(jid)
    if not vip_info:
        return False
        
    expiry_str = vip_info.get("expires_at")
    if not expiry_str:
        return True # VIP vitalício se não tiver data
        
    try:
        expiry_date = datetime.datetime.fromisoformat(expiry_str)
        return datetime.datetime.now() < expiry_date
    except:
        return False

def add_vip(jid, months=1):
    data = load_vip_data()
    now = datetime.datetime.now()
    
    if jid in data["vips"]:
        # Estende assinatura
        current_expiry = datetime.datetime.fromisoformat(data["vips"][jid]["expires_at"])
        if current_expiry < now: current_expiry = now
        new_expiry = current_expiry + datetime.timedelta(days=30 * months)
    else:
        new_expiry = now + datetime.timedelta(days=30 * months)
        
    data["vips"][jid] = {
        "added_at": now.isoformat(),
        "expires_at": new_expiry.isoformat()
    }
    return save_vip_data(data)

def is_group_allowed(jid):
    data = load_vip_data()
    return jid in data.get("allowed_groups", [])

def add_allowed_group(jid):
    data = load_vip_data()
    if jid not in data["allowed_groups"]:
        data["allowed_groups"].append(jid)
        return save_vip_data(data)
    return True
