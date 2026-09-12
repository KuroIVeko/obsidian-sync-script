import os, re, requests, json, base64, time, shutil
from requests.auth import HTTPBasicAuth

# --- 配置 ---
USER = os.getenv('DB_USER')
PASS = os.getenv('DB_PASS')
DB   = os.getenv('DB_NAME', 'vault')

# 【修改点】: 优先读取完整的 COUCHDB_URL，如果没有则尝试用旧逻辑拼接
COUCHDB_URL = os.getenv('COUCHDB_URL', '').rstrip('/')
DB_HOST = os.getenv('DB_HOST')

if COUCHDB_URL:
    # 如果用户给了完整地址 (如 http://192.168.1.10:5984)
    BASE_URL = f'{COUCHDB_URL}/{DB}'
elif DB_HOST:
    # 旧方式兼容 (如 http://obsidian_livesync:5984)
    BASE_URL = f'http://{DB_HOST}:5984/{DB}'
else:
    raise ValueError("Missing configuration: Please set COUCHDB_URL.")

TARGET_FOLDER = os.getenv('TARGET_FOLDER', '').strip('/')
OUT_DIR = '/blog_root/content/posts' 
POLL_INTERVAL = int(os.getenv('INTERVAL', 20))

PROTECTED_FILES = ['_index.md', '.gitignore']

print(f'[Init] Connecting to: {BASE_URL} (User: {USER})', flush=True)

AUTH = HTTPBasicAuth(USER, PASS)

if not os.path.exists(OUT_DIR): os.makedirs(OUT_DIR)

BASE64_RE = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')


def decode_chunk(part):
    """还原一个内容块。

    只有在能严格确认是 base64 时才解码：字符集、长度，以及重新编码后与
    原文完全一致（round-trip 校验）。其余一律原样返回。

    这样做的原因：base64.b64decode 默认（validate=False）会静默丢弃所有
    不在 base64 字符表里的字符——换行、空格、[ { < 引号都在此列。
    旧逻辑靠首字符猜测是否 base64，导致内容为单个换行符的块被解码成空
    字符串，Markdown 代码块因此被压成一行。
    """
    if not isinstance(part, str):
        return str(part)
    if not BASE64_RE.match(part) or len(part) < 4 or len(part) % 4 != 0:
        return part
    try:
        decoded = base64.b64decode(part, validate=True)
        if base64.b64encode(decoded).decode('ascii') != part:
            return part
        return decoded.decode('utf-8')
    except Exception:
        return part


def perform_sync():
    try:
        r = requests.get(f'{BASE_URL}/_all_docs?include_docs=true', auth=AUTH, timeout=60)
        if r.status_code != 200: return False

        data = r.json()
        rows = data.get('rows', [])
        
        chunk_map = {}
        meta_docs = []
        active_relative_paths = set()
        sync_count = 0

        for row in rows:
            doc = row.get('doc', {})
            doc_id = doc.get('_id', '')
            
            if doc.get('_deleted') or doc.get('deleted') or doc.get('type') == 'delete':
                continue

            chunk = doc.get('data') or doc.get('plain') or doc.get('content')
            if chunk:
                chunk_map[doc_id] = chunk
                if doc_id.startswith('h:'): chunk_map[doc_id[2:]] = chunk
            
            path_str = doc.get('path', '')
            if 'children' in doc and path_str and (TARGET_FOLDER.lower() in path_str.lower()):
                meta_docs.append(doc)

        for meta in meta_docs:
            full_obsidian_path = meta.get('path', '') 
            
            if TARGET_FOLDER and TARGET_FOLDER.lower() in full_obsidian_path.lower():
                try:
                    idx = full_obsidian_path.lower().index(TARGET_FOLDER.lower())
                    rel_path = full_obsidian_path[idx + len(TARGET_FOLDER):].lstrip('/')
                except:
                    rel_path = os.path.basename(full_obsidian_path)
            else:
                rel_path = full_obsidian_path

            if not rel_path: continue
            if not rel_path.endswith('.md'): rel_path += '.md'

            active_relative_paths.add(rel_path)

            children = meta.get('children', [])
            chunk_ids = children if isinstance(children, list) else list(children.keys())
            if not chunk_ids: continue

            raw_content = ''
            for cid in chunk_ids:
                part = chunk_map.get(cid) or chunk_map.get(f'h:{cid}')
                if part is not None:
                    raw_content += decode_chunk(part)

            if raw_content:
                clean_content = raw_content.replace('\ufeff', '').lstrip()
                
                local_abs_path = os.path.join(OUT_DIR, rel_path)
                local_dir = os.path.dirname(local_abs_path)
                
                if not os.path.exists(local_dir):
                    os.makedirs(local_dir, exist_ok=True)
                
                try:
                    need_write = True
                    if os.path.exists(local_abs_path):
                        with open(local_abs_path, 'r', encoding='utf-8') as f:
                            if f.read() == clean_content:
                                need_write = False
                    
                    if need_write:
                        print(f'[Sync] Write: {rel_path}', flush=True)
                        with open(local_abs_path, 'w', encoding='utf-8') as f:
                            f.write(clean_content)
                        sync_count += 1
                except Exception as e:
                    print(f'[Warn] Write Error {rel_path}: {e}', flush=True)

        # --- 清理逻辑 ---
        try:
            for root, dirs, files in os.walk(OUT_DIR):
                for filename in files:
                    if filename in PROTECTED_FILES or filename.startswith('.'): continue
                    if not filename.endswith('.md'): continue

                    abs_path = os.path.join(root, filename)
                    rel_from_root = os.path.relpath(abs_path, OUT_DIR)

                    rel_from_root = rel_from_root.replace(chr(92), '/')

                    if rel_from_root not in active_relative_paths:
                        print(f'[Delete] Clean: {rel_from_root}', flush=True)
                        os.remove(abs_path)
            
            for root, dirs, files in os.walk(OUT_DIR, topdown=False):
                for name in dirs:
                    try:
                        d_path = os.path.join(root, name)
                        if not os.listdir(d_path):
                            os.rmdir(d_path)
                    except: pass
        except Exception as e:
            print(f'[Warn] Cleanup Error: {e}', flush=True)

        if sync_count > 0:
            print(f'[Done] Updated {sync_count} files.', flush=True)
        return True

    except Exception as e:
        print(f'[Error] Loop Fatal: {e}', flush=True)
        return False

print(f'=== Recursive Sync Started (Target: {TARGET_FOLDER}) ===', flush=True)
perform_sync()

current_seq = 'now'
try:
    r = requests.get(f'{BASE_URL}/_changes?descending=true&limit=1', auth=AUTH, timeout=10)
    if r.status_code == 200: current_seq = r.json().get('last_seq', 'now')
except: pass

while True:
    time.sleep(POLL_INTERVAL)
    try:
        changes_url = f'{BASE_URL}/_changes?since={current_seq}&limit=1'
        r = requests.get(changes_url, auth=AUTH, timeout=10)
        if r.status_code == 200:
            resp = r.json()
            if resp.get('results'):
                # 稍微缓冲一下，防止连续写入导致频繁触发
                time.sleep(3)
                perform_sync()
                current_seq = resp.get('last_seq')
        else:
            print(f'[Warn] DB Check: {r.status_code}', flush=True)
    except Exception as e:
        print(f'[Error] Conn: {e}', flush=True)
        time.sleep(10)
